import { describe, expect, test } from "vitest";
import { comparisonPath, decodeRef, encodeRef, parseBrowseQuery, parseComparison, safeReturnPath } from "../../src/app/routes";

const ref = {namespace:"cleaned",snapshot_id:"a".repeat(64),source_id:"4"};
describe("V5 URL boundaries", () => {
  test("exact immutable references and their order survive comparison links", () => {
    const second = {...ref,source_id:"27"};
    expect(decodeRef(encodeRef(ref))).toEqual(ref);
    expect(parseComparison(comparisonPath([second,ref]).split("?")[1]!)).toEqual([second,ref]);
  });
  test.each(["ref=4",`ref=${encodeRef(ref)}&ref=${encodeRef(ref)}`,"owner=buyer",[1,2,3,4].map(i=>`ref=${encodeRef({...ref,source_id:String(i)})}`).join("&")])("rejects malformed, duplicate, private or over-limit comparison routes: %s",query=>{
    expect(parseComparison(query)).toBeNull();
  });
  test.each(["q=private+free+text","csrf_token=secret","make=A&make=B","cursor=opaque","snapshot=old","model=%00"]) ("rejects unsupported browse query: %s",query=>{
    expect(parseBrowseQuery(query).valid).toBe(false);
  });
  test("allows structured inventory filters and snapshot-bound cursors only",()=>{
    expect(parseBrowseQuery(`make=Mercedes-Benz&snapshot=${ref.snapshot_id}&cursor=opaque`).valid).toBe(true);
    expect(parseBrowseQuery("").valid).toBe(true);
  });
  test.each(["https://example.test/cars","//example.test","/draft/private","/cars#private","/cars?owner=a"])("return navigation cannot escape the public browse allowlist: %s",path=>{
    expect(safeReturnPath(path)).toBe("/cars");
  });
});
