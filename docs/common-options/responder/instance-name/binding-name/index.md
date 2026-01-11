---
title: Binding Name
parent: Instance Name
ancestor: Responder
nav_order: 1
---

## `[[[[binding-name]]]]`

This is a primary/remote binding name, and must match a name in the same `[[[instance-name]]]` section of the `[[Requester]]`.

### type

The main data binding is the binding that WeeWX uses to store the archive data.
Typically the data binding is 'wx_binding' and the database name is 'weewx'.
Valid values are 'main' or 'secondary'.
Default value is 'secondary'.
