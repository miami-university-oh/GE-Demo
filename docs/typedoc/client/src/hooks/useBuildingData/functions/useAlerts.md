[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/hooks/useBuildingData](../README.md) / useAlerts

# Function: useAlerts()

> **useAlerts**(): [`Alert`](../../../lib/buildingData/interfaces/Alert.md)[]

Defined in: [client/src/hooks/useBuildingData.ts:77](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/hooks/useBuildingData.ts#L77)

Returns all active alerts across the building, sorted newest-first by timestamp.
Re-renders the consumer on every simulation tick.

## Returns

[`Alert`](../../../lib/buildingData/interfaces/Alert.md)[]

Flat array of all [Alert](../../../lib/buildingData/interfaces/Alert.md) objects.
