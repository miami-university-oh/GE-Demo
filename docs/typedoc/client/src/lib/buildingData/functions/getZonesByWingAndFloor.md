[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/lib/buildingData](../README.md) / getZonesByWingAndFloor

# Function: getZonesByWingAndFloor()

> **getZonesByWingAndFloor**(`wing`, `floor`): [`Zone`](../interfaces/Zone.md)[]

Defined in: [client/src/lib/buildingData.ts:334](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/buildingData.ts#L334)

Filters zones by wing and floor.

## Parameters

### wing

[`Wing`](../type-aliases/Wing.md)

Target wing identifier (`'east'`, `'west'`, or `'north'`).

### floor

[`Floor`](../type-aliases/Floor.md)

Target floor (`0` = Basement, `1` = Ground Floor, `2` = Upper Floor).

## Returns

[`Zone`](../interfaces/Zone.md)[]

Zones matching both criteria.
