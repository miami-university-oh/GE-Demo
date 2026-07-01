[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/lib/buildingData](../README.md) / subscribeToZones

# Function: subscribeToZones()

> **subscribeToZones**(`fn`): () => `void`

Defined in: [client/src/lib/buildingData.ts:303](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/buildingData.ts#L303)

Subscribes to live zone updates. Starts the 3-second simulation timer when the first
subscriber registers, and stops it when the last subscriber unsubscribes.

## Parameters

### fn

() => `void`

Callback invoked on every simulation tick.

## Returns

An unsubscribe function; call it to remove the listener and stop the timer
         when no other subscribers remain.

() => `void`
