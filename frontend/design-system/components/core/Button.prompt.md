Groundwork's only button: white outline by default, survey-blue primary for the one main action, link for low-weight actions like "Sign out" or "Remove".
```jsx
<Button variant="primary">Email me a sign-in link</Button>
<Button>Choose files</Button>
<Button variant="link">Send another</Button>
```
- `size="small"` for inline Accept/Reject in review lists.
- `on` for the pressed state inside SegToggle.
- Labels are verbs in sentence case, and say what happens ("Share 3 files", not "Submit").
