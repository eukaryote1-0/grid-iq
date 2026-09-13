# BPC engineering data contract

GridIQ can operate as an open-data planning model without these fields. It cannot become a validated BPC operational power-flow / predictive-maintenance model until the following are supplied and reconciled.

## Network identity
- stable asset / bus / branch IDs
- substation name and geospatial coordinates
- in-service/out-of-service state and effective dates
- normally-open/closed switch state

## Transmission lines
- from bus / to bus
- nominal voltage (kV)
- circuit count
- conductor / bundle
- positive-sequence R and X (ohm or pu, with base)
- shunt susceptance/capacitance where required
- normal / emergency thermal rating (MVA or A)
- commissioning year

## Transformers
- HV/LV buses and nominal voltages
- MVA rating
- impedance / X/R
- vector group where relevant
- tap range, tap position and control mode
- normal / emergency rating

## Time-aligned operation
- timestamp and timezone
- bus/substation active demand MW
- reactive demand MVAr where AC validation is expected
- generator P/Q output and availability
- interchange / import MW by gateway
- breaker/switch state
- curtailment / load shedding markers

## Asset condition / risk
- commissioning date / age
- inspections and condition scores
- defects
- maintenance history
- forced and planned outages
- failure/event history with cause codes
- protection operations

## Validation artifacts
- reference one-line diagram
- EMS/SCADA topology snapshot corresponding to measurements
- agreed peak/off-peak snapshots
- utility load-flow case if available
- loss-accounting scope and boundary

Until these exist, GridIQ labels electrical values as observed, derived, benchmark, model output, or unknown. It never upgrades benchmark values to measured BPC facts.
