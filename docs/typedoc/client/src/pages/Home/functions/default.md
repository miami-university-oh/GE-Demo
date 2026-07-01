[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/pages/Home](../README.md) / default

# Function: default()

> **default**(): `Element`

Defined in: [client/src/pages/Home.tsx:46](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/pages/Home.tsx#L46)

Main IIoT dashboard page.

Composes the full SCADA-style layout: a fixed header with global KPIs,
a wing/zone navigation sidebar, a central FloorPlanViewer (elevation ↔ floor plan),
a slide-in ZonePanel for the selected zone, a collapsible wing overview, and a
scrolling alert ticker. Clicking the Makino zone (B0-MAK) replaces the layout with
the full-screen MakinoLab deep-dive view. The header clock ticks every second.

## Returns

`Element`
