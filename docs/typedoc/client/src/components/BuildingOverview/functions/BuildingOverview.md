[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/BuildingOverview](../README.md) / BuildingOverview

# Function: BuildingOverview()

> **BuildingOverview**(`zones`): `Element`

Defined in: [client/src/components/BuildingOverview.tsx:111](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/BuildingOverview.tsx#L111)

Collapsible bottom panel that renders a `WingCard` for each of the
East, West, and North wings. The panel can be toggled open/closed via
a header button; collapse state is managed with local state.

## Parameters

### zones

`BuildingOverviewProps`

All building zones; filtered per-wing before passing to WingCard.

## Returns

`Element`
