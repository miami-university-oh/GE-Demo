[**IIoT Building Dashboard — TypeScript API**](../../../../../README.md)

***

[IIoT Building Dashboard — TypeScript API](../../../../../README.md) / [client/src/components/Map](../README.md) / MapView

# Function: MapView()

> **MapView**(`className`): `Element`

Defined in: [client/src/components/Map.tsx:137](https://github.com/miami-university-oh/GE-Demo/blob/642ca7d0153183cb3416879175191a504039a85d/client/src/components/Map.tsx#L137)

Renders a full Google Map inside a `div` container. On mount, loads
the Maps SDK via `loadMapScript`, instantiates a `google.maps.Map`
with the provided center and zoom, and calls `onMapReady` with the
map instance so callers can imperatively control the map (add markers,
listen for events, etc.).

## Parameters

### className

`MapViewProps`

Additional CSS classes for the map container div.

## Returns

`Element`
