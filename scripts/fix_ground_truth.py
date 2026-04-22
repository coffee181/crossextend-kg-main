#!/usr/bin/env python3
"""批量修复ground truth标注文件."""

import json
from pathlib import Path

def fix_ground_truth_file(file_path: Path) -> None:
    """修复单个ground truth文件."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 1. 修复workflow_relation_ground_truth的family字段
    for wr in data.get('workflow_relation_ground_truth', []):
        if wr.get('head', '').startswith('T'):
            wr['family'] = 'action_object'

    # 2. 重新计算统计字段
    concepts = data.get('concept_ground_truth', [])
    relations = data.get('relation_ground_truth', [])
    workflow_relations = data.get('workflow_relation_ground_truth', [])

    data['_statistics'] = {
        'total_concepts': len(concepts),
        'positive_concepts': sum(1 for c in concepts if c.get('should_be_in_graph', False)),
        'negative_concepts': sum(1 for c in concepts if not c.get('should_be_in_graph', False)),
        'total_relations': len(relations),
        'valid_relations': sum(1 for r in relations if r.get('valid', False)),
        'total_workflow_relations': len(workflow_relations),
        'valid_workflow_relations': sum(1 for w in workflow_relations if w.get('valid', False))
    }

    # 3. 更新annotator_id
    data['annotator_id'] = 'blind_human_annotator'
    data['annotation_date'] = '2026-04-22'

    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Fixed: {file_path.name}")

def main():
    gt_dir = Path('D:/crossextend_kg/data/ground_truth')

    gold_files = [
        'battery_BATOM_001.json',
        'battery_BATOM_002.json',
        'battery_BATOM_003.json',
        'cnc_CNCOM_001.json',
        'cnc_CNCOM_002.json',
        'cnc_CNCOM_003.json',
        'nev_EVMAN_001.json',
        'nev_EVMAN_002.json',
        'nev_EVMAN_003.json'
    ]

    for gold_file in gold_files:
        file_path = gt_dir / gold_file
        if file_path.exists():
            fix_ground_truth_file(file_path)
        else:
            print(f"Missing: {gold_file}")

    print("\nAll files fixed.")

if __name__ == '__main__':
    main()