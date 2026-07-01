[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/AlertTicker](../README.md) / AlertTicker

# Function: AlertTicker()

> **AlertTicker**(`alerts`): `Element`

Defined in: [client/src/components/AlertTicker.tsx:22](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/AlertTicker.tsx#L22)

Renders a 28 px tall horizontal scrolling ticker bar.
When `alerts` is non-empty, shows up to 12 real alerts in a seamlessly
looping marquee; alert severity drives the icon and dot color
(critical → red, warn → amber, ok → green). When `alerts` is empty,
displays three "all nominal" placeholder status messages instead.

## Parameters

### alerts

`AlertTickerProps`

Active building alerts to display in the ticker.

## Returns

`Element`
