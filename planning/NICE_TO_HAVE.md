# Nice-to-Have Features (Post-MVP)

Features and improvements identified during development that are valuable but not essential for MVP.

---

## Events Generator: Timezone Handling

**Current Implementation:**
- USPS events use a fixed offset (-05:00 EST)
- All USPS events across all labels use the same timezone offset
- Realistic but simplistic

**Improvement:**
- Implement realistic timezone distribution across US regions
- Use 3+ different US timezones (EST, CST, MST, PST) based on:
  - Label origin_zip code (calculate timezone from ZIP)
  - Or randomly assign from major US timezone regions
- Each label's events should use consistent timezone (don't mix timezones for same shipment)
- More realistic: different regions have different local times

**Impact:**
- Higher realism: events from different regions use their local times
- Slightly more complex: need ZIP-to-timezone lookup or region-based mapping
- Does NOT affect data quality testing (only formatting)

**Effort Level:** Low-to-Medium
**Priority:** Nice-to-have (current fixed offset is sufficient for testing)

---

## Timestamp Randomness

**Current Implementation:**
- All events get ±2 hours randomness

**Future Considerations:**
- Different randomness per event type (pickup might be less random than delivery)
- Randomness based on carrier SLA reliability (some carriers more punctual)

---

## Location ZIP Generation

**Current Implementation:**
- Random 5-digit ZIP
- No relationship to label origin_zip or dest_zip

**Improvement:**
- Location ZIP should be closer to shipment route (origin → destination)
- Or match origin_zip for pickup, dest_zip for delivery

**Effort Level:** Low
**Priority:** Nice-to-have

---

## Event Sequence Realism

**Current Implementation:**
- All carriers follow same strict 4-event sequence: `picked_up` → `in_transit` → `out_for_delivery` → `delivered`
- Events always occur in this exact order
- No carrier-specific variations

**Real-World Issues:**
- Different carriers use different event sequences (USPS has more granular scans than UPS)
- Events can be skipped (some packages go directly to delivery without explicit in_transit)
- Events can be out of logical order (package scanned back to facility, then forward again)
- Events can repeat (same event type at different locations)
- Some events might be missing entirely for certain packages

**Improvement:**
- Implement carrier-specific event sequences
- Allow event skipping (not all packages have all events)
- Allow logical reordering (realistic messiness)
- Add facility scans/returns

**Effort Level:** Medium-to-High
**Priority:** Nice-to-have (current sequence sufficient for testing data pipeline)

---

## Event Timing Realism

**Current Implementation:**
- Events are strictly evenly distributed across SLA window
- Timing: 15%, 40%, 75%, 95% of SLA
- Regular intervals between events
- Realistic only in the aggregate (average SLA respected)

**Real-World Issues:**
- Events are highly irregular (long gaps, then rapid cluster)
- Pickup can happen hours or days after label creation
- In-transit events can span hours or days with no pattern
- Final delivery often happens very close to last scan (minutes before arrival)
- Timing varies wildly by carrier, route, day of week

**Improvement:**
- Add realistic event clustering (multiple scans within hours, then day-long gaps)
- Vary timing based on carrier reliability
- Add weekday/weekend behavior (Friday deliveries slower)
- Realistic pickup delays (some packages sit for hours)

**Effort Level:** Medium
**Priority:** Nice-to-have (current distribution is analytically reasonable)

---

## Raw Payload

**Current Implementation:**
- All events have NULL raw_payload

**Improvement:**
- Generate realistic carrier JSON payloads per carrier format
- Include carrier-specific fields (tracking number, handler, weight, etc.)
- High realism but low test value

**Effort Level:** Medium
**Priority:** Nice-to-have

---
