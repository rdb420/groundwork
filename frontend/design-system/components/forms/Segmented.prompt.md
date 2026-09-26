Two to four short, mutually exclusive answers in one row.
```jsx
<Segmented name="pi" value={pi} onChange={setPi} options={[["yes","Yes"],["no","No"],["unsure","Not sure"]]} />
<Segmented small name="mode" value={mode} onChange={setMode} options={[["listen","Map the conversation"],["command","Only my instructions"]]} />
```
