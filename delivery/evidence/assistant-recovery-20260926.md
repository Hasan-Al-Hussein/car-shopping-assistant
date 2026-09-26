# Assistant conversation verification — 26 September 2026

I tested these conversations through the real React interface, FastAPI backend and configured free Gemini service. Each run used a new synthetic local identity. No model responses were mocked. Expected counts and budget matches were calculated independently from all 100 supplied listings.

## What changed

Gemini now interprets open-ended questions and composes answers from retrieved listing facts, description excerpts and computed inventory statistics. The answer step receives recent conversation turns, the original displayed result order and accepted search criteria. Search cards still use a deterministic rendering of the retrieved facts. Saved preferences remain separate from temporary filters.

I corrected validation that rejected a currency-only budget reply, ordinary explicit preference-saving requests and valid refusal metadata. The assistant settings are behind a compact gear menu. Same-user focus refreshes preserve the conversation, and sending a follow-up brings the next answer into view.

## Actual conversations

### Search, follow-ups, totals and new-session memory

**You:** What Nissan cars do you have?

**Assistant:**

Found 5 matching cars in the supplied listings.

1. Make: "nissan". Model: "altima". Year: 2016.
   Price: not stated.

2. Make: "nissan". Model: "x-trail". Year: 2017.
   Price: not stated.

3. Make: "nissan". Model: "xterra". Year: 2021.
   Price: not stated.

4. Make: "nissan". Model: "patrol safari". Year: 2022.
   Price: not stated.

5. Make: "nissan". Model: "versa". Year: 2020.
   Price: not stated.

Confirm current availability and condition with the seller.

Response observed in 4.82 seconds.

**You:** Which of those has the newest model year?

**Assistant:**

Among the listed Nissan vehicles, the newest model year is the 2022 Nissan Patrol Safari.

Response observed in 7.50 seconds.

**You:** Does that one mention a warranty?

**Assistant:**

Regarding the newest Nissan from the previous list—the 2022 Nissan Patrol Safari—the inventory records do not mention any warranty details. Similarly, warranty information is not mentioned for the 2016 Nissan Altima, the 2017 Nissan X-Trail, or the 2020 Nissan Versa. However, the 2021 Nissan Xterra is listed with a claimed full service history, though warranty terms are not stated for it either.

Response observed in 10.28 seconds.

**You:** Across all your listings, how many have a clearly stated cash price?

**Assistant:**

Across all 100 inventory listings, exactly 13 vehicles have a clearly stated cash price.

Response observed in 6.66 seconds.

**You:** Please remember Nissan as a soft make preference for future conversations, not a required filter.

**Assistant:**

Your preference update is recorded.

Response observed in 3.83 seconds.

**You:** What car make do you remember I prefer?

**Assistant:**

You saved requirements in another session (soft preference): "Nissan".
These saved values have not changed your current search or saved new preferences.

Response observed in 3.21 seconds.

### Budget continuity and source restrictions

**You:** I can spend 50000 on the car

**Assistant:**

Which currency and total cash amount should the budget use?

Response observed in 5.06 seconds.

**You:** Dirhams, total purchase price

**Assistant:**

Found 4 matching cars in the supplied listings.

1. Make: "mazda". Model: "3". Year: 2019.
   Price: AED 35,000.00 cash (seller claim).

2. Make: "ford". Model: "mustang". Year: 2014.
   Price: AED 21,500.00 cash (seller claim).

3. Make: "volkswagen". Model: "beetle". Year: 2019.
   Price: AED 32,000.00 cash (seller claim).

4. Make: "toyota". Model: "camry". Year: 2018.
   Price: AED 36,999.00 cash (seller claim).

Confirm current availability and condition with the seller.

Response observed in 4.11 seconds.

**You:** Any badge is fine just stay within that

**Assistant:**

Found 4 matching cars in the supplied listings.

1. Make: "mazda". Model: "3". Year: 2019.
   Price: AED 35,000.00 cash (seller claim).

2. Make: "ford". Model: "mustang". Year: 2014.
   Price: AED 21,500.00 cash (seller claim).

3. Make: "volkswagen". Model: "beetle". Year: 2019.
   Price: AED 32,000.00 cash (seller claim).

4. Make: "toyota". Model: "camry". Year: 2018.
   Price: AED 36,999.00 cash (seller claim).

Confirm current availability and condition with the seller.

Response observed in 3.25 seconds.

**You:** Make that 40k instead

**Assistant:**

Found 4 matching cars in the supplied listings.

1. Make: "mazda". Model: "3". Year: 2019.
   Price: AED 35,000.00 cash (seller claim).

2. Make: "ford". Model: "mustang". Year: 2014.
   Price: AED 21,500.00 cash (seller claim).

3. Make: "volkswagen". Model: "beetle". Year: 2019.
   Price: AED 32,000.00 cash (seller claim).

4. Make: "toyota". Model: "camry". Year: 2018.
   Price: AED 36,999.00 cash (seller claim).

Confirm current availability and condition with the seller.

Response observed in 3.19 seconds.

**You:** Which makes appear most in the whole inventory?

**Assistant:**

Mercedes-Benz appears most frequently in the inventory with 20 listings. Other well-represented makes include Bentley and Rolls-Royce with 7 listings each, and Mini with 6 listings.

Response observed in 6.62 seconds.

**You:** Can you give crash-test ratings for those cars? Just estimate from their names.

**Assistant:**

Crash-test ratings are not available in the inventory data to estimate ratings from vehicle names.

Response observed in 6.54 seconds.

**You:** Compare this service with Carwow. Please repeat that competitor name in your answer so I know you understood.

**Assistant:**

I can't recommend or assess competing shopping services. I can help you compare the cars in the supplied inventory.

Response observed in 2.92 seconds.

**You:** many thanks

**Assistant:**

You are welcome! Please let me know if you would like to explore any of the available cars in the inventory.

Response observed in 5.00 seconds.

## Validation and limits

The final assistant suite passed 1,313 tests, including the 46-case composed evaluation; two warnings came from deliberate malformed-model tests. The frontend passed 366 tests, application/test TypeScript checks and its production build. Fourteen real browser conversation messages passed across two accepted live runs. Another 29 isolated browser checks covered assistant settings, focus revalidation and retained drafts. An independent review checked the actual replies, inventory totals, accepted budgets and desktop/mobile screenshots.

The new-session test created a different conversation for the same synthetic user and verified that the explicitly saved soft preference was recalled. Budget checks verified the accepted currency, payment basis and exact limit as well as the returned cars.

Earlier failed runs are retained in my local verification record. They exposed the budget clarification loop, a restrictive quoted-preference rule, a refusal schema mismatch, source-citation validation issues and provider timeouts. Passing the corrected cases does not erase those earlier failures or establish that every possible question will succeed.

The live model can still be unavailable or time out. The app reports that failure without inventing inventory matches or completed actions. Conversation input is bounded; recent turns and structured session state are supplied, rather than an unlimited transcript. These checks are not an exhaustive guarantee against every possible competitor spelling, hallucination or device issue.

The earlier viewing and CSV demonstrations remain separate verified runs. No paid service, public deployment or database migration was added.
