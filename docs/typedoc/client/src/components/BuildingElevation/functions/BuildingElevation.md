[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/BuildingElevation](../README.md) / BuildingElevation

# Function: BuildingElevation()

> **BuildingElevation**(`zones`): `Element`

Defined in: [client/src/components/BuildingElevation.tsx:291](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/BuildingElevation.tsx#L291)

Renders an interactive isometric 3D overview of the T-shaped building.
Each floor (Basement, Floor 1, Floor 2) is drawn as a stacked slab with
status-colored top faces, vertical wall faces, window rows, and status
indicator pillars. Hovering a slab highlights it; clicking calls
`onSelectFloor` to drill into that floor's 2D plan.

## Parameters

### zones

`BuildingElevationProps`

All building zones used to derive per-floor status and temperature.

## Returns

`Element`
