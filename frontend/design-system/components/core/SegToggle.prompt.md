Joined toggle buttons for switching the map side panel; clicking the active one closes it.
```jsx
<SegToggle ariaLabel="Panels" value={panel} onChange={setPanel}
  items={[["live","Live"],["rules","Rules"],["doc","Document"],["session","Recording ●"],["ai","AI drafts"]]} />
```
Append " •" to a label when that panel has a new proposal, " ●" while recording.
