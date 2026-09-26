# Connections, minimum connection times and baggage (summary for the prototype)

Minimum connection times (MCT) in the prototype are illustrative. Real MCTs are published per airport and terminal pair by each airport and in industry schedule data; verify before use.

## Minimum connection time
The minimum connection time is the shortest interval between an arriving and a departing flight that an airline will sell as a valid connection at that airport. It depends on the airport, the terminals, the airlines and whether the connection crosses a border. A connection shorter than the MCT cannot be booked, so the prototype treats it as infeasible.

## Schengen border at Zürich
Switzerland and Poland are both in the Schengen Area. A traveller arriving in Zürich from Boston enters Schengen in Zürich and must pass passport control there before a flight to Warsaw; the Warsaw arrival is then treated as a domestic Schengen arrival. The non-Schengen to Schengen transfer takes longer than a Schengen to Schengen transfer, which the connection buffer should reflect.

## Checked baggage on a through ticket
When all flights are on one ticket, checked bags are through-checked to the final destination and follow the passenger's re-booking automatically, although bags can miss tight connections and arrive on a later flight.

## Checked baggage on separate tickets
With separate tickets the traveller must collect bags, exit, and check in again for the next flight. Allow substantially more time, and check the second airline's bag allowance and fees.

## Cancellations
A cancelled flight removes every connection that depends on it. The prototype estimates cancellation probability with the delay model and treats a cancellation as a failed plan that triggers the fallback cascade.
