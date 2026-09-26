Labelled form control in Groundwork style: bold question as label, quiet "Optional" hint, "For example: …" placeholder.
```jsx
<Field label="What is it?" defaultValue="Arrears tracker" />
<Field label="What do you use it for?" hint="Optional" as="textarea"
  placeholder="For example: I update this every Monday from the bank statement, then email it to Dean." />
<Field label="How often is it used?" as="select" options={[["","Not sure"],["weekly","Weekly"]]} />
```
Labels are questions a staff member would answer, not database field names.
