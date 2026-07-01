[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/hooks/useBuildingData](../README.md) / useZone

# Function: useZone()

> **useZone**(`id`): [`Zone`](../../../lib/buildingData/interfaces/Zone.md) \| `undefined`

Defined in: [client/src/hooks/useBuildingData.ts:61](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/hooks/useBuildingData.ts#L61)

Returns a single [Zone](../../../lib/buildingData/interfaces/Zone.md) by ID, or `undefined` if the ID is null or not found.
Re-renders the consumer on every simulation tick.

## Parameters

### id

`string` \| `null`

Zone identifier, or `null` to opt out.

## Returns

[`Zone`](../../../lib/buildingData/interfaces/Zone.md) \| `undefined`

The matching Zone, or `undefined`.
