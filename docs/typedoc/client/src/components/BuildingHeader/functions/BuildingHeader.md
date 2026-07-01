[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/BuildingHeader](../README.md) / BuildingHeader

# Function: BuildingHeader()

> **BuildingHeader**(`summary`): `Element`

Defined in: [client/src/components/BuildingHeader.tsx:162](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/BuildingHeader.tsx#L162)

Top header bar for the IIoT Building Dashboard.
Renders (left to right): brand identity, zone status dot counts,
KPI chips (power / temperature / occupancy), HAAS + UR5e machine
bridge badges, a UR5e dashboard navigation button, a critical-alert
count badge (when applicable), a live activity indicator, the current
time, and a logout button.

## Parameters

### summary

`BuildingHeaderProps`

Aggregated building metrics (zone counts, energy, temp, occupancy).

## Returns

`Element`
