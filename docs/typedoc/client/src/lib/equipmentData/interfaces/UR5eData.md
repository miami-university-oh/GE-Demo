[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/lib/equipmentData](../README.md) / UR5eData

# Interface: UR5eData

Defined in: [client/src/lib/equipmentData.ts:83](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L83)

## Properties

### alarms

> **alarms**: `string`[]

Defined in: [client/src/lib/equipmentData.ts:103](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L103)

***

### collaborativeMode

> **collaborativeMode**: `boolean`

Defined in: [client/src/lib/equipmentData.ts:97](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L97)

***

### cyclesComplete

> **cyclesComplete**: `number`

Defined in: [client/src/lib/equipmentData.ts:98](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L98)

***

### cycleTime

> **cycleTime**: `number`

Defined in: [client/src/lib/equipmentData.ts:99](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L99)

***

### cycleTimeTotal

> **cycleTimeTotal**: `number`

Defined in: [client/src/lib/equipmentData.ts:100](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L100)

***

### history

> **history**: `object`[]

Defined in: [client/src/lib/equipmentData.ts:104](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L104)

#### payload

> **payload**: `number`

#### power

> **power**: `number`

#### t

> **t**: `number`

#### tcpSpeed

> **tcpSpeed**: `number`

***

### humanProximity

> **humanProximity**: `number`

Defined in: [client/src/lib/equipmentData.ts:96](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L96)

***

### id

> **id**: `"ur5e"`

Defined in: [client/src/lib/equipmentData.ts:84](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L84)

***

### joints

> **joints**: [`CobotJoint`](CobotJoint.md)[]

Defined in: [client/src/lib/equipmentData.ts:94](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L94)

***

### mode

> **mode**: `"manual"` \| `"automatic"` \| `"freedrive"` \| `"paused"`

Defined in: [client/src/lib/equipmentData.ts:89](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L89)

***

### name

> **name**: `"UR5e Cobot"`

Defined in: [client/src/lib/equipmentData.ts:85](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L85)

***

### payload

> **payload**: `number`

Defined in: [client/src/lib/equipmentData.ts:92](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L92)

***

### payloadMax

> **payloadMax**: `number`

Defined in: [client/src/lib/equipmentData.ts:93](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L93)

***

### powerKw

> **powerKw**: `number`

Defined in: [client/src/lib/equipmentData.ts:101](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L101)

***

### program

> **program**: `string`

Defined in: [client/src/lib/equipmentData.ts:88](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L88)

***

### safetyStatus

> **safetyStatus**: `"normal"` \| `"reduced"` \| `"protective_stop"` \| `"emergency_stop"`

Defined in: [client/src/lib/equipmentData.ts:95](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L95)

***

### status

> **status**: [`MachineStatus`](../type-aliases/MachineStatus.md)

Defined in: [client/src/lib/equipmentData.ts:87](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L87)

***

### tcpPosition

> **tcpPosition**: [`AxisPosition`](AxisPosition.md) & `object`

Defined in: [client/src/lib/equipmentData.ts:91](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L91)

#### Type Declaration

##### rx

> **rx**: `number`

##### ry

> **ry**: `number`

##### rz

> **rz**: `number`

***

### tcpSpeed

> **tcpSpeed**: `number`

Defined in: [client/src/lib/equipmentData.ts:90](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L90)

***

### temperature

> **temperature**: `number`

Defined in: [client/src/lib/equipmentData.ts:102](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L102)

***

### type

> **type**: `"Cobot"`

Defined in: [client/src/lib/equipmentData.ts:86](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/lib/equipmentData.ts#L86)
