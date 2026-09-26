Library/Coverage table.
```jsx
<DataTable columns={[{key:"title",label:"File"},{key:"proc",label:"Process"},{key:"files",label:"Files",num:true}]}
  rows={rows} onRowClick={setOpen} />
```
Put the filename as bold text with a quiet second line (original name · size) via `render`.
