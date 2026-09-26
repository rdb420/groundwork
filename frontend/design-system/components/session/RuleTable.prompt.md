Conditions live in rule tables, not chains of decisions (Real-Life BPMN).
```jsx
<RuleTable name="Arrears reminder" inputs={["Days late"]} outputs={["Action"]}
  rows={[["1–3","Friendly SMS"],["4–7","Breach notice"],["14+","Tribunal"]]} />
```
