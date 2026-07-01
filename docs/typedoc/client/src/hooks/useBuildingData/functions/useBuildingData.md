[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/hooks/useBuildingData](../README.md) / useBuildingData

# Function: useBuildingData()

> **useBuildingData**(): `object`

Defined in: [client/src/hooks/useBuildingData.ts:29](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/hooks/useBuildingData.ts#L29)

Subscribes to live zone updates and exposes building data utilities.

Re-renders the consumer on every simulation tick. The `getZonesByWingAndFloor` and
`getZoneById` callbacks are recreated each tick so they always reflect the latest
zone state while remaining referentially stable within a single render.

## Returns

`object`

An object with:
- `zones` — current Zone array snapshot.
- `summary` — aggregate building statistics.
- `alerts` — all active alerts sorted newest-first.
- `getZonesByWingAndFloor(wing, floor)` — filtered zone lookup.
- `getZoneById(id)` — single-zone lookup by ID.

### alerts

> **alerts**: [`Alert`](../../../lib/buildingData/interfaces/Alert.md)[]

### getZoneById

> **getZoneById**: (`id`) => [`Zone`](../../../lib/buildingData/interfaces/Zone.md) \| `undefined`

#### Parameters

##### id

`string`

#### Returns

[`Zone`](../../../lib/buildingData/interfaces/Zone.md) \| `undefined`

### getZonesByWingAndFloor

> **getZonesByWingAndFloor**: (`wing`, `floor`) => [`Zone`](../../../lib/buildingData/interfaces/Zone.md)[]

#### Parameters

##### wing

[`Wing`](../../../lib/buildingData/type-aliases/Wing.md)

##### floor

[`Floor`](../../../lib/buildingData/type-aliases/Floor.md)

#### Returns

[`Zone`](../../../lib/buildingData/interfaces/Zone.md)[]

### summary

> **summary**: `object`

#### summary.avgTemp

> **avgTemp**: `number`

#### summary.critical

> **critical**: `number`

#### summary.offline

> **offline**: `number`

#### summary.ok

> **ok**: `number`

#### summary.total

> **total**: `number`

#### summary.totalEnergy

> **totalEnergy**: `number`

#### summary.totalOccupancy

> **totalOccupancy**: `number`

#### summary.warn

> **warn**: `number`

### zones

> **zones**: [`Zone`](../../../lib/buildingData/interfaces/Zone.md)[]
