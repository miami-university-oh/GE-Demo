[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/contexts/ThemeContext](../README.md) / ThemeProvider

# Function: ThemeProvider()

> **ThemeProvider**(`children`): `Element`

Defined in: [client/src/contexts/ThemeContext.tsx:31](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/contexts/ThemeContext.tsx#L31)

Applies the active theme class to `document.documentElement` and provides theme
context to the subtree.

When `switchable` is `true`, the selected theme is persisted to `localStorage` and
a `toggleTheme` function is exposed via context. When `switchable` is `false` (default),
the theme is locked to `defaultTheme` and `toggleTheme` is `undefined`.

## Parameters

### children

`ThemeProviderProps`

React subtree that consumes theme context.

## Returns

`Element`
