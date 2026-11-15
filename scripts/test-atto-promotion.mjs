import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import test from "node:test";

const get = (path) => readFileSync(new URL("../" + path, import.meta.url), "utf8");
const manifest = JSON.parse(get("docs/atto-candidate-promotion.v1.json"));
const modules = get(".gitmodules");
const approvedPins = {
  "packages/act-clients": "149b1af3be7447f2babf3fbcc1e45289f0d492b7",
  "packages/act-interfaces": "611828bcd6ceee863914854805d252e8ecbf871a"
};
function committedGitlink(path) {
  const result = execFileSync("git", ["ls-tree", "HEAD", "--", path], {encoding:"utf8"}).trim();
  const match = result.match(/^160000 commit ([a-f0-9]{40})\\t/);
  return match?.[1] ?? null;
}


function candidateErrors(p) {
  const errors = [];
  const check = (ok, message) => { if (!ok) errors.push(message); };
  check(p.schema === "anticaptrad.atto-candidate-promotion/v1", "schema identity");
  check(p.status === "candidate", "unapproved production promotion");
  check(p.allowDeploy === false && p.allowSdkPublish === false, "unapproved deploy or SDK publish");
  check(p.requireExecutableCompilerReceipt === true, "compiler evidence required");
  check(p.requirePeerSchemaParity === true, "peer authorities required");
  check(JSON.stringify(p.authoritativeRepositories) === JSON.stringify([
    "anticaptrad/act-interfaces", "anticaptrad/act-clients",
  ]), "authority ownership");
  check(JSON.stringify(p.candidatePullRequests) === JSON.stringify([
    "https://github.com/anticaptrad/act-interfaces/pull/18",
    "https://github.com/anticaptrad/act-clients/pull/26",
  ]), "candidate evidence links");
  for (const [path, pinned] of Object.entries(approvedPins)) {
    check(p.approvedAggregatePins?.[path] === pinned, "approved gitlink pin changed");
  }
  return errors;
}

test("aggregate Atto candidate promotion stays blocked and sources remain separate submodules", () => {
  assert.deepEqual(candidateErrors(manifest), []);
  for (const name of ["act-clients", "act-interfaces"]) {
    assert.ok(modules.includes(`[submodule "packages/${name}"]`));
    assert.ok(modules.includes(`https://github.com/anticaptrad/${name}.git`));
  }
  assert.ok(!modules.includes("atto-candidate"));
  for (const [path, sha] of Object.entries(approvedPins)) {
    assert.equal(committedGitlink(path), sha, path + " changed before admission");
  }
});

test("candidate promotion guard rejects forged production and missing evidence", () => {
  for (const changed of [
    {...manifest, allowDeploy:true},
    {...manifest, allowSdkPublish:true},
    {...manifest, status:"production"},
    {...manifest, requireExecutableCompilerReceipt:false},
    {...manifest, requirePeerSchemaParity:false},
    {...manifest, authoritativeRepositories:["anticaptrad/act-clients"]},
    {...manifest, approvedAggregatePins:{...manifest.approvedAggregatePins, "packages/act-clients":"forged"}},
  ]) {
    assert.notDeepEqual(candidateErrors(changed), []);
  }
});
