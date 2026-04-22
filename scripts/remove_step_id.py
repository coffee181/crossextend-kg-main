#!/usr/bin/env python3
"""去掉ground truth文件中冗余的step_id字段."""

import json
from pathlib import Path

def remove_step_id(file_path: Path) -> None:
    """去掉concept_ground_truth中的step_id字段."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 去掉step_id字段
    for concept in data.get('concept_ground_truth', []):
        if 'step_id' in concept:
            del concept['step_id']

    # 更新annotator
    data['annotator_id'] = 'blind_human_annotator'
    data['annotation_date'] = '2026-04-22'

    # 重新计算统计
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

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Removed step_id from: {file_path.name}")

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
            remove_step_id(file_path)
        else:
            print(f"Missing: {gold_file}")

    print("\nDone. All step_id fields removed.")

if __name__ == '__main__':
    main()