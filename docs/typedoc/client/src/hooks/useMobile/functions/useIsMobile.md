[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/hooks/useMobile](../README.md) / useIsMobile

# Function: useIsMobile()

> **useIsMobile**(): `boolean`

Defined in: [client/src/hooks/useMobile.tsx:13](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/hooks/useMobile.tsx#L13)

Returns `true` when the viewport width is less than 768 px.

Subscribes to a `matchMedia` listener so the value updates reactively whenever
the viewport crosses the breakpoint — no polling required.

## Returns

`boolean`

`true` if the current viewport is mobile-sized, `false` otherwise.
