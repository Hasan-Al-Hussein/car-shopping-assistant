import { useState } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { BrowserServices } from "../../src/app/BrowserServices";
import { ServicesProvider } from "../../src/app/ServicesProvider";
import {
  ConversationPanel,
  pageConversationContext,
} from "../../src/features/conversation/ConversationPanel";
import { ConversationAnswer } from "../../src/features/conversation/ConversationContent";
import { CinemaHeader } from "../../src/shared/ui/CinemaHeader";
import { ContextualAssistant } from "../../src/shared/ui/inner/ContextualAssistant";
import { listingPath } from "../../src/app/routes";
import type { ResponseOf, Schema } from "../../src/shared/api/contracts";
import { config, identity, meta, searchResult } from "./apiFixtures";
import {
  conversationEnvelope as envelope,
  conversationId as id,
  conversationResult,
  conversationSession,
  transcriptPage,
  transcriptTurn,
} from "./conversationFixtures";
import { viewingDraft } from "./viewingFixtures";
import { deferred } from "../harness/fixtures";

const services: BrowserServices[] = [];
afterEach(() => {
  cleanup();
  services.splice(0).forEach((service) => service.dispose());
});
const flush = async () => {
  await act(async () => {
    for (let index = 0; index < 20; index += 1) await Promise.resolve();
    await vi.advanceTimersByTimeAsync(1);
  });
};
async function setup() {
  const service = new BrowserServices();
  services.push(service);
  const state = {
    session: conversationSession(),
    page: transcriptPage(),
    health: "ready" as Schema<"Capability">["state"],
    healthReason: null as string | null,
  };
  vi.spyOn(service.api, "revalidateIdentity").mockImplementation(async () => {
    service.owner.accept(service.owner.capture().epoch, identity());
    return envelope(identity());
  });
  const read = vi
    .spyOn(service.api, "read")
    .mockImplementation(async (operation) => {
      if (operation === "get_session")
        return envelope(structuredClone(state.session));
      if (operation === "get_session_messages")
        return envelope(structuredClone(state.page));
      if (operation === "get_config") return config();
      if (operation === "get_health")
        return {
          meta: meta(),
          data: {
            service: "car-shopping-assistant" as const,
            inventory: { state: "ready" as const, reason: null },
            store: { state: "ready" as const, reason: null },
            viewing: { state: "ready" as const, reason: null },
            export: { state: "ready" as const, reason: null },
            assistant: {
              state: state.health,
              reason:
                state.healthReason ??
                (state.health === "ready"
                  ? null
                  : "Synthetic unavailable service"),
            },
            active_snapshot_id: null,
          },
        };
      throw Error(`UNSCRIPTED_READ:${operation}`);
    });
  const write = vi
    .spyOn(service.api, "mutate")
    .mockRejectedValue(Error("UNSCRIPTED_MUTATION"));
  service.start();
  await flush();
  await service.readSession(id);
  return { service, state, read, write };
}
function Harness({ service }: { service: BrowserServices }) {
  const [open, setOpen] = useState(true);
  return (
    <ServicesProvider services={service}>
      <MemoryRouter>
        <button onClick={() => setOpen((value) => !value)}>
          Toggle conversation
        </button>
        {open && (
          <ConversationPanel
            openIdentity={() => {}}
            close={() => setOpen(false)}
          />
        )}
      </MemoryRouter>
    </ServicesProvider>
  );
}

describe("U3 actual conversation components with synthetic services; no rendered-browser claim", () => {
  test.each(["current", "absent", "old"] as const)(
    "pending clarification stays visible without duplication: %s transcript",
    async (history) => {
      const { service, state } = await setup();
      const question = "Which currency should I use?";
      const pending = {
        kind: "clarification" as const,
        intent_id: "90000000-0000-4000-8000-000000000001",
        created_revision: 1,
        purpose: "search_criteria" as const,
        targets: ["budget" as const],
        question,
      };
      state.session = {
        ...state.session,
        revision: 1,
        pending_intent: pending,
      };
      const result = {
        ...conversationResult(),
        text: question,
        pending_intent: {
          ...pending,
          intent_id:
            history === "old"
              ? "90000000-0000-4000-8000-000000000002"
              : pending.intent_id,
        },
      };
      state.page = transcriptPage(
        history === "absent" ? [] : [transcriptTurn(result)],
        1,
      );
      await service.readSession(id);
      render(<Harness service={service} />);
      await flush();
      expect(screen.getAllByText(question)).toHaveLength(
        history === "old" ? 2 : 1,
      );
      const reply = screen.getByRole("checkbox", {
        name: "Reply to this exact clarification",
      });
      expect(reply).toBeChecked();
      fireEvent.click(reply);
      expect(reply).not.toBeChecked();
    },
  );
  test.each([
    "configured_not_verified",
    "Assistant access is configured but not yet verified.",
  ])(
    "configured but unverified health uses neutral startup copy without claiming online: %s",
    async (reason) => {
      const { service, state, write } = await setup();
      state.health = "degraded";
      state.healthReason = reason;
      render(<Harness service={service} />);
      await flush();
      fireEvent.click(
        screen.getByRole("button", { name: "Assistant settings" }),
      );
      expect(
        screen.getByText("Ask about a car, or explore your options."),
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/temporarily unavailable|online/i),
      ).not.toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Send message" }),
      ).toBeEnabled();
      expect(write).not.toHaveBeenCalled();
    },
  );

  test("anonymous onboarding is read-only until checked consent and explicit Enable chat", async () => {
    const { service, write } = await setup();
    vi.mocked(service.api.revalidateIdentity).mockImplementation(async () => {
      const anonymous = {
        state: "anonymous",
        notice_version: "DEMO-POLICY-1",
      } as const;
      service.owner.accept(service.owner.invalidate(), anonymous);
      return { meta: meta(), data: anonymous };
    });
    await act(async () => {
      await service.revalidate();
    });
    const bootstrap = vi.spyOn(service, "bootstrap").mockResolvedValue();
    const createSession = vi
      .spyOn(service, "createSession")
      .mockResolvedValue();
    render(<Harness service={service} />);
    await flush();
    const enable = screen.getByRole("button", { name: "Enable chat" });
    expect(enable).toBeDisabled();
    expect(bootstrap).not.toHaveBeenCalled();
    expect(createSession).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: "I understand and agree to enable browser access for chat and saving.",
      }),
    );
    expect(enable).toBeEnabled();
    expect(bootstrap).not.toHaveBeenCalled();
    fireEvent.click(enable);
    expect(bootstrap).toHaveBeenCalledExactlyOnceWith(
      "DEMO-POLICY-1",
      true,
      "",
    );
    expect(createSession).not.toHaveBeenCalled();
  });

  test("a suggested starter fills an editable draft without sending it", async () => {
    const { service, write } = await setup();
    const send = vi.spyOn(service.conversation, "send").mockResolvedValue();
    render(<Harness service={service} />);
    await flush();
    const prompt = "Help me find a car within my budget";
    fireEvent.click(screen.getByRole("button", { name: prompt }));
    expect(
      screen.getByLabelText("Message the car-shopping assistant"),
    ).toHaveValue(prompt);
    expect(send).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
  });

  test("settings stay outside the transcript and composer, and close with Escape", async () => {
    const { service, write } = await setup();
    render(<Harness service={service} />);
    await flush();
    const region = screen.getByRole("region", {
      name: "Conversation transcript",
    });
    const composer = screen.getByLabelText(
      "Message the car-shopping assistant",
    );
    expect(
      screen.getAllByRole("region", { name: "Conversation transcript" }),
    ).toHaveLength(1);
    expect(region.contains(composer)).toBe(false);
    expect(screen.queryByText("Conversation options")).not.toBeInTheDocument();
    const settings = screen.getByRole("button", { name: "Assistant settings" });
    expect(region.contains(settings)).toBe(false);
    fireEvent.click(settings);
    await flush();
    const popup = screen.getByRole("dialog", { name: "Assistant settings" });
    expect(region.contains(popup)).toBe(false);
    expect(screen.getByRole("tab", { name: "Chat" })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("tab", { name: "Chat" }), {
      key: "ArrowRight",
    });
    expect(screen.getByRole("tab", { name: "Context" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Context" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    fireEvent.keyDown(popup, { key: "Escape" });
    await flush();
    expect(
      screen.queryByRole("dialog", { name: "Assistant settings" }),
    ).not.toBeInTheDocument();
    expect(settings).toHaveFocus();
    expect(composer.closest(".conversation-workspace")).toBe(
      region.parentElement,
    );
    fireEvent.change(composer, { target: { value: "A focused unsent draft" } });
    composer.focus();
    fireEvent.scroll(region);
    expect(composer).toHaveFocus();
    expect(composer).toHaveValue("A focused unsent draft");
    expect(write).not.toHaveBeenCalled();
  });
  test.each(["success", "read failure"] as const)(
    "refresh preserves its focusable control, unsent text and duplicate guard through %s",
    async (settlement) => {
      const { service, state, read, write } = await setup();
      const refresh = vi.spyOn(service.conversation, "refresh");
      render(<Harness service={service} />);
      await flush();
      fireEvent.click(
        screen.getByRole("button", { name: "Assistant settings" }),
      );
      refresh.mockClear();
      const composer = screen.getByLabelText(
        "Message the car-shopping assistant",
      );
      fireEvent.change(composer, {
        target: { value: "Keep these unsent words" },
      });
      const button = screen.getByRole("button", {
        name: "Refresh conversation",
      });
      const gate = deferred<ResponseOf<"get_session">>();
      read.mockImplementationOnce(() => gate.promise);
      button.focus();
      act(() => {
        fireEvent.click(button);
        fireEvent.click(button);
      });
      await flush();
      expect(refresh).toHaveBeenCalledTimes(1);
      expect(button).not.toBeDisabled();
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button).toHaveAttribute("aria-busy", "true");
      expect(button).toHaveFocus();
      expect(
        screen.getByText("Reading this conversation…"),
      ).toBeInTheDocument();
      fireEvent.click(button);
      expect(refresh).toHaveBeenCalledTimes(1);
      await act(async () => {
        if (settlement === "read failure")
          gate.reject(Error("Synthetic read failure"));
        else gate.resolve(envelope(state.session));
      });
      await flush();
      expect(screen.getByRole("button", { name: "Refresh conversation" })).toBe(
        button,
      );
      expect(button).toHaveFocus();
      expect(button).toHaveAttribute("aria-busy", "false");
      expect(button).toHaveAttribute("aria-disabled", "false");
      expect(composer).toHaveValue("Keep these unsent words");
      expect(
        screen.getByRole("region", { name: "Conversation transcript" }),
      ).toHaveAttribute("tabindex", "0");
      if (settlement === "read failure")
        expect(
          screen.getByText(/current conversation could not be read/),
        ).toBeInTheDocument();
      fireEvent.click(button);
      await flush();
      expect(refresh).toHaveBeenCalledTimes(2);
      expect(write).not.toHaveBeenCalled();
    },
  );

  test("opening is read-only; Enter/Shift+Enter/IME and visible Send have distinct behavior", async () => {
    const { service, write } = await setup(),
      send = vi.spyOn(service.conversation, "send").mockResolvedValue();
    render(<Harness service={service} />);
    await flush();
    const composer = screen.getByLabelText(
      "Message the car-shopping assistant",
    );
    expect(write).not.toHaveBeenCalled();
    fireEvent.change(composer, {
      target: { value: "Which source facts remain unknown?" },
    });
    fireEvent.keyDown(composer, { key: "Enter", shiftKey: true });
    expect(send).not.toHaveBeenCalled();
    fireEvent.compositionStart(composer);
    fireEvent.keyDown(composer, {
      key: "Enter",
      keyCode: 229,
      isComposing: true,
    });
    expect(send).not.toHaveBeenCalled();
    fireEvent.compositionEnd(composer);
    fireEvent.keyDown(composer, { key: "Enter" });
    expect(send).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(send).toHaveBeenCalledTimes(2);
  });
  test("closing and reopening preserves unsent words; owner reset hides them", async () => {
    const { service } = await setup();
    render(<Harness service={service} />);
    await flush();
    fireEvent.change(
      screen.getByLabelText("Message the car-shopping assistant"),
      { target: { value: "Private unsent words" } },
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Toggle conversation" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Toggle conversation" }),
    );
    await flush();
    expect(
      screen.getByLabelText("Message the car-shopping assistant"),
    ).toHaveValue("Private unsent words");
    act(() => service.owner.invalidate());
    await flush();
    expect(
      screen.queryByLabelText("Message the car-shopping assistant"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Private unsent words")).not.toBeInTheDocument();
  });
  test("reopening refreshes cached unavailable health without sending the preserved draft", async () => {
    const { service, state, write, read } = await setup();
    const send = vi.spyOn(service.conversation, "send").mockResolvedValue();
    state.health = "unavailable";
    render(<Harness service={service} />);
    await flush();
    const healthReads = () =>
      read.mock.calls.filter((call) => call[0] === "get_health");
    expect(healthReads()).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    fireEvent.change(
      screen.getByLabelText("Message the car-shopping assistant"),
      { target: { value: "Keep my question until I send it" } },
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Toggle conversation" }),
    );
    await flush();
    state.health = "ready";
    const readyHealth = deferred<ResponseOf<"get_health">>();
    const readImplementation = read.getMockImplementation()!;
    read.mockImplementation((operation, request) =>
      operation === "get_health"
        ? readyHealth.promise
        : readImplementation(operation, request),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Toggle conversation" }),
    );
    await flush();
    expect(healthReads()).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Check assistant service" }),
    ).toBeDisabled();
    await act(async () => {
      readyHealth.resolve(await readImplementation("get_health", {}));
    });
    await flush();
    expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();
    expect(
      screen.getByLabelText("Message the car-shopping assistant"),
    ).toHaveValue("Keep my question until I send it");
    fireEvent.click(screen.getByRole("button", { name: "Assistant settings" }));
    expect(
      screen.getByRole("button", { name: "Check assistant service" }),
    ).toBeEnabled();
    expect(healthReads()).toHaveLength(2);
    expect(send).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
  });
  test("cached service outage has an explicit read-only recovery control", async () => {
    const { service, state, write, read } = await setup();
    state.health = "unavailable";
    render(<Harness service={service} />);
    await flush();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    state.health = "ready";
    fireEvent.click(
      screen.getByRole("button", { name: "Check assistant service" }),
    );
    await flush();
    expect(screen.getByRole("button", { name: "Send message" })).toBeEnabled();
    expect(
      read.mock.calls.filter((call) => call[0] === "get_health"),
    ).toHaveLength(2);
    expect(write).not.toHaveBeenCalled();
  });
  test("a settled answer exposes its beginning locally while keeping the focused unsent draft", async () => {
    const { service, state, write } = await setup();
    render(<Harness service={service} />);
    await flush();
    const region = screen.getByRole("region", {
      name: "Conversation transcript",
    });
    const composer = screen.getByLabelText(
      "Message the car-shopping assistant",
    );
    Object.defineProperties(region, {
      scrollHeight: { configurable: true, value: 2000 },
      clientHeight: { configurable: true, value: 200 },
    });
    region.scrollTop = 1800;
    fireEvent.scroll(region);
    fireEvent.change(composer, { target: { value: "Keep my next question" } });
    composer.focus();
    const bounds = vi
      .spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockImplementation(function (this: HTMLElement) {
        return new DOMRect(
          0,
          this === region
            ? 200
            : this.classList.contains("conversation-assistant-message")
              ? 270
              : 0,
          300,
          100,
        );
      });
    try {
      state.session.revision = 1;
      state.page = transcriptPage([transcriptTurn(conversationResult())], 1);
      await act(async () => {
        await service.conversation.refresh(id);
      });
      expect(region.scrollTop).toBe(1870);
      expect(region.scrollTop).not.toBe(region.scrollHeight);
      expect(composer).toHaveFocus();
      expect(composer).toHaveValue("Keep my next question");
      expect(write).not.toHaveBeenCalled();
    } finally {
      bounds.mockRestore();
    }
  });
  test("a reader above the end gets a new-response control without forced focus or scroll", async () => {
    const { service, state } = await setup();
    render(<Harness service={service} />);
    await flush();
    const region = screen.getByRole("region", {
      name: "Conversation transcript",
    });
    Object.defineProperties(region, {
      scrollHeight: { configurable: true, value: 1000 },
      clientHeight: { configurable: true, value: 200 },
    });
    region.scrollTop = 100;
    fireEvent.scroll(region);
    state.session.revision = 1;
    state.page = transcriptPage([transcriptTurn(conversationResult())], 1);
    await act(async () => {
      await service.conversation.refresh(id);
    });
    expect(region.scrollTop).toBe(100);
    expect(region).not.toHaveFocus();
    const showLatest = screen.getByRole("button", {
      name: "New response — show latest",
    });
    expect(region).not.toContainElement(showLatest);
    expect(region.parentElement).toContainElement(showLatest);
    fireEvent.click(showLatest);
    expect(region.scrollTop).toBe(1000);
    expect(region).toHaveFocus();
  });
  test("explicitly sending resumes following after a long answer while later deliberate scrolling still pauses it", async () => {
    const { service, state } = await setup();
    const send = vi.spyOn(service.conversation, "send").mockResolvedValue();
    render(<Harness service={service} />);
    await flush();
    const region = screen.getByRole("region", {
      name: "Conversation transcript",
    });
    const composer = screen.getByLabelText(
      "Message the car-shopping assistant",
    );
    Object.defineProperties(region, {
      scrollHeight: { configurable: true, value: 2400 },
      clientHeight: { configurable: true, value: 400 },
    });
    region.scrollTop = 100;
    fireEvent.scroll(region);
    state.session.revision = 1;
    state.page = transcriptPage([transcriptTurn(conversationResult())], 1);
    await act(async () => {
      await service.conversation.refresh(id);
    });
    expect(
      screen.getByRole("button", { name: "New response — show latest" }),
    ).toBeInTheDocument();
    fireEvent.change(composer, { target: { value: "Which one is newest?" } });
    composer.focus();
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(send).toHaveBeenCalledOnce();
    expect(
      screen.queryByRole("button", { name: "New response — show latest" }),
    ).not.toBeInTheDocument();
    const bounds = vi
      .spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockImplementation(function (this: HTMLElement) {
        return new DOMRect(
          0,
          this === region
            ? 200
            : this.classList.contains("conversation-assistant-message")
              ? 900
              : 0,
          300,
          100,
        );
      });
    try {
      state.session.revision = 2;
      const second = transcriptTurn(
        conversationResult(undefined, {
          client_message_id: crypto.randomUUID(),
          turn_revision: 2,
          current_revision: 2,
          text: "The newest one is the 2022 model.",
        }),
      );
      state.page = transcriptPage([...state.page.items, second], 2);
      await act(async () => {
        await service.conversation.refresh(id);
      });
      expect(region.scrollTop).toBe(800);
      expect(composer).toHaveFocus();
      expect(
        screen.queryByRole("button", { name: "New response — show latest" }),
      ).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Send message" }));
      region.scrollTop = 50;
      fireEvent.scroll(region);
      state.session.revision = 3;
      state.page = transcriptPage(
        [
          ...state.page.items,
          transcriptTurn(
            conversationResult(undefined, {
              client_message_id: crypto.randomUUID(),
              turn_revision: 3,
              current_revision: 3,
              text: "Its listing does not mention a warranty.",
            }),
          ),
        ],
        3,
      );
      await act(async () => {
        await service.conversation.refresh(id);
      });
      expect(region.scrollTop).toBe(50);
      expect(
        screen.getByRole("button", { name: "New response — show latest" }),
      ).toBeInTheDocument();
    } finally {
      bounds.mockRestore();
    }
  });
  test("settings hide an old conversation-start notice once messages exist", async () => {
    const { service, state } = await setup();
    const notice =
      "A new local conversation has started. Saved preferences remain separate; no earlier selected car has been imported.";
    vi.spyOn(service, "getSnapshot").mockReturnValue({
      ...service.getSnapshot(),
      notice,
    });
    state.session.revision = 1;
    state.page = transcriptPage([transcriptTurn(conversationResult())], 1);
    render(<Harness service={service} />);
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "Assistant settings" }));
    expect(screen.queryByText(notice)).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "New conversation" }),
    ).toBeInTheDocument();
  });
  test("enlarged outer scrolling preserves a reader then jumps the actual scroll owner", async () => {
    const { service, state } = await setup();
    render(<Harness service={service} />);
    await flush();
    const region = screen.getByRole("region", {
      name: "Conversation transcript",
    });
    const owner = region.closest<HTMLElement>(".conversation-panel")!;
    owner.style.overflowY = "auto";
    region.style.overflowY = "visible";
    Object.defineProperties(owner, {
      scrollHeight: { configurable: true, value: 2000 },
      clientHeight: { configurable: true, value: 440 },
    });
    owner.scrollTop = 100;
    region.scrollTop = 77;
    fireEvent.scroll(owner);
    state.session.revision = 1;
    state.page = transcriptPage([transcriptTurn(conversationResult())], 1);
    await act(async () => {
      await service.conversation.refresh(id);
    });
    expect(owner.scrollTop).toBe(100);
    expect(region).not.toHaveFocus();
    fireEvent.click(
      screen.getByRole("button", { name: "New response — show latest" }),
    );
    expect(owner.scrollTop).toBe(2000);
    expect(region.scrollTop).toBe(77);
    expect(region).toHaveFocus();
  });

  test("new-session recall shows actual returned values and strength", async () => {
    const { service } = await setup();
    render(<Harness service={service} />);
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "Assistant settings" }));
    fireEvent.click(screen.getByRole("tab", { name: "Preferences" }));
    expect(screen.getByText(/makes: Synthetic · soft/)).toBeInTheDocument();
    expect(
      screen.getByText(/Cash budget \(AED\): any–20000/),
    ).toBeInTheDocument();
  });
  test("prose never creates saved-action feedback and answer text is not parsed as HTML", async () => {
    const { service } = await setup(),
      result = conversationResult(undefined, {
        text: 'Saved preferences! <img src=x onerror="alert(1)">',
      });
    render(
      <ServicesProvider services={service}>
        <MemoryRouter>
          <ConversationAnswer
            result={result}
            onContext={() => {}}
            close={() => {}}
          />
        </MemoryRouter>
      </ServicesProvider>,
    );
    expect(screen.getByText(result.text)).toBeInTheDocument();
    expect(
      screen.queryByText(/Preferences saved locally/),
    ).not.toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });
  test("only typed success shows saved preferences and viewing proposals link to the shared exact review", async () => {
    const { service } = await setup(),
      draft = viewingDraft(),
      result = conversationResult(undefined, {
        actions: {
          preferences: {
            state: "succeeded",
            client_action_id: crypto.randomUUID(),
            result: conversationSession().recalled_preferences,
          },
          shortlist: { state: "not_requested" },
          lead: { state: "not_requested" },
        },
        pending_intent: {
          kind: "viewing_review",
          draft_id: draft.draft_id,
          review_id: draft.review!.review_id,
          operation_key: draft.review!.operation_key,
        },
      });
    render(
      <ServicesProvider services={service}>
        <MemoryRouter>
          <ConversationAnswer
            result={result}
            onContext={() => {}}
            close={() => {}}
          />
        </MemoryRouter>
      </ServicesProvider>,
    );
    expect(
      screen.getByText("Preferences saved locally · revision 2."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Open exact viewing review" }),
    ).toHaveAttribute("href", `/viewings/drafts/${draft.draft_id}/review`);
    expect(
      screen.queryByRole("button", { name: /confirm/i }),
    ).not.toBeInTheDocument();
  });
  test("page context retains exact references and never borrows search ordinals for comparison", () => {
    const proof = searchResult().data.presentation,
      ref = proof.ordered_refs[0]!;
    expect(pageConversationContext(listingPath(ref), proof)).toMatchObject({
      selectedRef: ref,
      presentation: proof,
    });
    expect(pageConversationContext("/compare", proof)).toBeNull();
    expect(
      pageConversationContext(
        listingPath({ ...ref, source_id: "unrelated" }),
        proof,
      )?.presentation,
    ).toBeNull();
  });
  test("result context buttons disclose that an original command is still busy", async () => {
    const { service } = await setup(),
      result = conversationResult(undefined, { search: searchResult().data }),
      context = vi.fn();
    render(
      <ServicesProvider services={service}>
        <MemoryRouter>
          <ConversationAnswer
            result={result}
            onContext={context}
            close={() => {}}
            contextDisabled
          />
        </MemoryRouter>
      </ServicesProvider>,
    );
    expect(
      screen.queryByText("Search criteria and source coverage"),
    ).not.toBeInTheDocument();
    for (const button of screen.getAllByRole("button", {
      name: "Ask about this",
    }))
      expect(button).toBeDisabled();
    expect(context).not.toHaveBeenCalled();
  });
  test("home and comparison assistant entries call the shared panel opener", () => {
    vi.stubGlobal(
      "ResizeObserver",
      class {
        observe() {}
        disconnect() {}
      },
    );
    const open = vi.fn();
    render(
      <MemoryRouter>
        <CinemaHeader count={0} path="/" onAssistant={open} />
        <ContextualAssistant
          count={0}
          ready={false}
          preview={false}
          onVerify={() => {}}
          onInspect={() => {}}
          onOpen={open}
        >
          <p>Next steps</p>
        </ContextualAssistant>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Ask AI" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Open car-shopping conversation" }),
    );
    expect(open).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByPlaceholderText("Conversation unavailable"),
    ).not.toBeInTheDocument();
  });
});
