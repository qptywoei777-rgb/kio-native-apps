import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('grid_runtime', ROOT/'scripts/audit_grid_runtime_messages.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimeMessageGate(unittest.TestCase):
    def test_unavailable_or_empty_source_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=runtime.report(Path(tmp))
            self.assertFalse(result['sourceAvailable'])
            self.assertFalse(result['complete'])

    def test_literal_and_formatted_diagnostics_are_distinct_from_comments_and_wire_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp); folder=source/'crates/engine/src/cmd'; folder.mkdir(parents=True)
            (folder/'test.rs').write_text('''
                // bad("ignored", "not a real error")
                bad("wire.identifier", "no such window");
                bad(cmd, format!("not a range: {value}"));
                EngineError::Other(format!("{path}: {error}"));
                #[cfg(test)] mod tests { bad(cmd, "test only"); }
            ''', encoding='utf-8')
            rows=runtime.inventory(source)
            self.assertEqual({(r['source'],r['dynamic']) for r in rows}, {('no such window',False),('not a range: {value}',True),('{path}: {error}',True)})
            report=runtime.report(source)
            self.assertFalse(report['complete'])
            self.assertEqual(report['pendingTemplates'],2)
            self.assertEqual(report['opaqueOnlyTemplates'],1)


if __name__ == '__main__':
    unittest.main()
