[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/ZonePanel](../README.md) / ZonePanel

# Function: ZonePanel()

> **ZonePanel**(`zone`): `Element`

Defined in: [client/src/components/ZonePanel.tsx:242](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/ZonePanel.tsx#L242)

Right-side detail panel for a selected building zone. Renders:
- A status/location header with zone name and description.
- A 2-column metric grid (temperature, humidity, CO₂, power, occupancy, AQI).
- A row of radial gauges (humidity, air quality, network, equipment).
- A network load progress bar.
- An equipment online/total bar.
- Three 60-minute sparkline trend charts (temperature, energy, CO₂).
- An active alerts list (shown only when alerts exist).
- A zone ID / timestamp footer.

## Parameters

### zone

`ZonePanelProps`

The zone whose data is displayed.

## Returns

`Element`
