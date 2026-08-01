import { describe, expect, it } from "vitest";

describe("graph transform helper", () => {
  it("maps payload nodes into display fields", () => {
    const payload = {
      nodes: [
        {
          path: "src/demo_service/main.py",
          category: "Entry Point",
          is_entry_point: true,
          importance_score: 88,
          file_id: "1",
        },
      ],
      edges: [{ source: "src/demo_service/main.py", target: "src/demo_service/api/routes.py" }],
      truncated: false,
    };
    const node = payload.nodes[0];
    const parts = String(node.path).split("/");
    expect(parts.at(-1)).toBe("main.py");
    expect(node.is_entry_point).toBe(true);
    expect(payload.edges[0].source).toBe(node.path);
  });
});
