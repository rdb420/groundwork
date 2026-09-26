import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Button, DataTable, Dialog, Field, Status, Tag, artifactTone } from "../ui";

const html = (node: React.ReactNode) => renderToStaticMarkup(<MemoryRouter>{node}</MemoryRouter>);

describe("ui components", () => {
  it("renders buttons that don't submit forms unless asked", () => {
    expect(html(<Button>Go</Button>)).toBe('<button type="button" class="gw-btn">Go</button>');
    expect(html(<Button variant="primary" type="submit">Go</Button>)).toBe('<button type="submit" class="gw-btn gw-btn--primary">Go</button>');
  });

  it("maps a shared file's status to a pill tone", () => {
    expect(artifactTone("processed")).toBe("ok");
    expect(artifactTone("failed")).toBe("error");
    expect(artifactTone("quarantined")).toBe("info");
    expect(html(<Status tone="error">Needs a look</Status>)).toContain('class="gw-status s-failed"');
    expect(html(<Tag kind="pi" />)).toBe('<span class="gw-pi">Personal info</span>');
  });

  it("only makes table rows focusable when they open something", () => {
    const rows = [{ id: "a", name: "Rent roll", count: 0 }];
    const columns = [{ key: "name", label: "File" }, { key: "count", label: "Count", num: true }];
    const still = html(<DataTable rows={rows} columns={columns} />);
    expect(still).not.toContain("tabindex");
    expect(still).not.toContain("clickable");
    expect(still).toContain('<td class="num zero">·</td>');
    const open = html(<DataTable rows={rows} columns={columns} onRowClick={() => {}} />);
    expect(open).toContain('<tr class="clickable" tabindex="0">');
  });

  it("labels a dialog by its title and makes it a form when it submits", () => {
    const out = html(<Dialog title="Before you start" onSubmit={() => {}}><p>Hi</p></Dialog>);
    expect(out).toContain('<form class="gw-dialog" role="dialog" aria-modal="true" aria-labelledby="gw-dialog-title"');
    expect(out).toContain('<h2 id="gw-dialog-title">Before you start</h2>');
  });

  it("puts a field's hint after its label", () => {
    expect(html(<Field label="Why" hint="Optional" value="" onChange={() => {}} />))
      .toBe('<label class="gw-field">Why <span class="quiet">Optional</span><input class="gw-input" value=""/></label>');
  });
});
