[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/FloorPlanViewer](../README.md) / FloorPlanViewer

# Function: FloorPlanViewer()

> **FloorPlanViewer**(`zones`): `Element`

Defined in: [client/src/components/FloorPlanViewer.tsx:79](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/FloorPlanViewer.tsx#L79)

Two-mode building viewer with framer-motion transitions.

- **Elevation mode** (default): renders a 3D `BuildingElevation` overview.
  Clicking a floor triggers an 80 ms transition into floor plan mode.
- **Floor plan mode**: renders the 2D `FloorPlan` for the active floor.
  A back button returns to elevation mode; a floor switcher in the
  toolbar allows jumping between Basement, Floor 1, and Floor 2.

A bottom-left breadcrumb badge indicates the active floor level when
in floor plan mode.

## Parameters

### zones

`FloorPlanViewerProps`

All building zones passed through to the child viewers.

## Returns

`Element`
