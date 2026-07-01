[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/pages/MakinoLab](../README.md) / MakinoLab

# Function: MakinoLab()

> **MakinoLab**(`onBack`): `Element`

Defined in: [client/src/pages/MakinoLab.tsx:985](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/pages/MakinoLab.tsx#L985)

Makino Lab deep-dive page for the Advanced Manufacturing Hub.

Subscribes to both `equipmentStore` (lathe, cobot, three Makino machines,
bridge status) and `cameraStore` (CAM-01, CAM-02) on mount and mirrors
their state into local React state so each child panel re-renders on
update. Renders a header summary bar, a lab floor-map SVG with clickable
equipment icons, collapsible machine data panels for all six machines,
and two `CameraTile` components for the YOLO camera feeds.

## Parameters

### onBack

`MakinoLabProps`

Callback invoked when the user navigates back to the
                main Building Dashboard.

## Returns

`Element`
