Drop target for sharing files; always paired with a button for people who don't drag.
```jsx
<DropZone onFiles={add} />
<DropZone accept=".xlsx,.xlsm,.xls,.csv" label="Drop a workbook here, or" button="Choose a workbook" multiple={false} />
```
