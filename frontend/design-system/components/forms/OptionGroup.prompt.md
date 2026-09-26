Radio cards for choices that need a sentence of explanation.
```jsx
<OptionGroup name="layer" value={layer} onChange={setLayer} options={[
  { value: "declared", label: "How it's meant to be done", hint: "An official procedure, policy or training material." },
  { value: "actual", label: "How I actually do it", hint: "My own notes, checklist or the file I work from." },
  { value: "unsure", label: "Not sure", hint: "That's fine. We'll work it out together." },
]} />
```
