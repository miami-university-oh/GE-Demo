[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/pages/UR5eDashboard](../README.md) / default

# Function: default()

> **default**(): `Element`

Defined in: [client/src/pages/UR5eDashboard.tsx:17](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/pages/UR5eDashboard.tsx#L17)

UR5e RTDE Dashboard page.

Probes `http://localhost:8080` every 3 seconds to check whether the
Python `ur5e_dashboard.py` Dash server is running. Renders an inline
iframe when the server is online, or an "offline" placeholder with a
manual refresh button when it is not. A toolbar provides a back
navigation link to the Building Dashboard.

## Returns

`Element`
