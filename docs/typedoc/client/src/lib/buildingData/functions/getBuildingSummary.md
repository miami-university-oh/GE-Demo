[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/lib/buildingData](../README.md) / getBuildingSummary

# Function: getBuildingSummary()

> **getBuildingSummary**(): `object`

Defined in: [client/src/lib/buildingData.ts:367](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/buildingData.ts#L367)

Computes aggregate building statistics from the current zone snapshot.

## Returns

`object`

An object containing:
- `total` — total zone count.
- `ok / warn / critical / offline` — zone counts per status.
- `totalEnergy` — sum of all zone energy readings in kW.
- `totalOccupancy` — sum of all zone occupancy counts.
- `avgTemp` — mean temperature across all zones in °C.

### avgTemp

> **avgTemp**: `number`

### critical

> **critical**: `number`

### offline

> **offline**: `number`

### ok

> **ok**: `number`

### total

> **total**: `number`

### totalEnergy

> **totalEnergy**: `number`

### totalOccupancy

> **totalOccupancy**: `number`

### warn

> **warn**: `number`
