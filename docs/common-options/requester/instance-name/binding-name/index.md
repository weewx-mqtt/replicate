---
title: Binding Name
parent: Instance Name
ancestor: Requester
nav_order: 1
---

## `[[[[binding-name]]]]`

This is a primary/remote binding name, and must match a name in the same `[[[instance-name]]]` section of the `[[Responder]]`.
A replicating instance consists of a primary (source) and secondary (target) databases to replicate.

### direct_update

Controls if data for the `main` binding updates the database directly or is used to create an archive record.
Might be useful when running in 'standalone' mode.
Default is `False`.

### initialize

Controls if a new database is created when the database specified by the `secondary_binding` does not exists.
Default value is `true`.

### type

The main data binding is the binding that WeeWX uses to store the archive data.
Typically the data binding is 'wx_binding' and the database name is 'weewx'.
Valid values are 'main' or 'secondary'.
Default value is 'secondary'.

### secondary_data_binding

This is the target/local database binding.
It is the binding used by the requester to store the data.
