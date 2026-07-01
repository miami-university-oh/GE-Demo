[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/FloorPlan](../README.md) / FloorPlan

# Function: FloorPlan()

> **FloorPlan**(`zones`): `Element`

Defined in: [client/src/components/FloorPlan.tsx:408](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/FloorPlan.tsx#L408)

Renders an architectural 2D floor plan for a single building floor as
an inline SVG. Each room rectangle is color-coded by its zone's live
status, with a selected highlight and a hover highlight. Clicking a
room calls `onSelectZone` with the zone ID. Door arcs, stairwells,
elevators, and a compass rose are drawn as architectural annotations.
A tooltip shows zone name and current temperature on hover.

## Parameters

### zones

`FloorPlanProps`

All building zones (filtered to the active floor internally).

## Returns

`Element`
