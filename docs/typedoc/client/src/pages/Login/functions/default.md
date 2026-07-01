[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/pages/Login](../README.md) / default

# Function: default()

> **default**(): `Element`

Defined in: [client/src/pages/Login.tsx:11](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/pages/Login.tsx#L11)

Full-screen login page for the IIoT Building Dashboard.
Submits credentials to `useAuth().login` with a 400 ms artificial delay
to show a loading state. Displays an inline error message on invalid
credentials. On success, `AuthGate` re-renders and redirects the user
to the app without an explicit navigation call.

## Returns

`Element`
