import { abortable } from "./abort";
import { ClientFailure } from "./ClientFailure";

/** One screen's changing read intent; never use this to retry a mutation. */
export class LatestRead {
  #sequence = 0;
  #controller?: AbortController;

  async run<T>(read: (signal: AbortSignal) => Promise<T>): Promise<T> {
    this.cancel();
    const sequence = this.#sequence;
    const controller = new AbortController();
    this.#controller = controller;
    const result = await abortable(read(controller.signal), controller.signal);
    if (sequence !== this.#sequence)
      throw new ClientFailure("superseded", "read");
    return result;
  }

  cancel(): void {
    this.#sequence += 1;
    this.#controller?.abort(new ClientFailure("superseded", "read"));
  }
}
