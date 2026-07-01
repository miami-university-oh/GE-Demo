[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/lib/buildingData](../README.md) / getAllAlerts

# Function: getAllAlerts()

> **getAllAlerts**(): [`Alert`](../interfaces/Alert.md)[]

Defined in: [client/src/lib/buildingData.ts:353](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/buildingData.ts#L353)

Collects all alerts from every zone and returns them sorted newest-first by timestamp.

## Returns

[`Alert`](../interfaces/Alert.md)[]

Flat array of all active [Alert](../interfaces/Alert.md) objects across the building.
