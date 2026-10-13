import { describe, expect, it } from "vitest";
import { demoCreate, demoList } from "./demo";
describe("demo data separation", () => {
  it("filters synthetic jobs by their actual status", () => {
    expect(demoList("FAILED").items.every((j) => j.status === "FAILED")).toBe(
      true,
    );
    expect(demoList("FAILED").items.length).toBeGreaterThan(0);
  });
  it("creates unique synthetic jobs with the requested validation rules", () => {
    const input = {
      name: "Demo report",
      filename: "demo.csv",
      size: 100,
      required_columns: ["name"],
      numeric_columns: ["amount"],
    };
    const first = demoCreate(input),
      second = demoCreate(input);
    expect(first.job_id).not.toBe(second.job_id);
    expect(first.required_columns).toEqual(["name"]);
    expect(first.status).toBe("CREATED");
  });
});
