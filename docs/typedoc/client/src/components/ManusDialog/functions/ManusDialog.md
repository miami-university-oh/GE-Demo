[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/ManusDialog](../README.md) / ManusDialog

# Function: ManusDialog()

> **ManusDialog**(`title`): `Element`

Defined in: [client/src/components/ManusDialog.tsx:38](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/ManusDialog.tsx#L38)

Modal dialog prompting the user to log in with Manus.

Supports both controlled and uncontrolled open modes:
- **Controlled**: pass `open` + `onOpenChange`; the parent owns visibility state.
- **Uncontrolled**: omit `onOpenChange`; internal state mirrors the initial `open` prop.

Calls `onLogin` when the "Login with Manus" button is clicked, and
`onClose` (if provided) whenever the dialog is dismissed.

## Parameters

### title

`ManusDialogProps`

Optional dialog title text.

## Returns

`Element`
