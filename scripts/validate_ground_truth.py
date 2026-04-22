#!/usr/bin/env python3
"""验证ground truth标注文件的统计字段和格式."""

import json
from pathlib import Path

def validate_ground_truth_file(file_path: Path) -> dict:
    """验证单个ground truth文件."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    errors = []

    # 1. 验证统计字段
    concepts = data.get('concept_ground_truth', [])
    relations = data.get('relation_ground_truth', [])
    workflow_relations = data.get('workflow_relation_ground_truth', [])
    stats = data.get('_statistics', {})

    # 计算实际数量
    actual_total_concepts = len(concepts)
    actual_positive_concepts = sum(1 for c in concepts if c.get('should_be_in_graph', False))
    actual_negative_concepts = sum(1 for c in concepts if not c.get('should_be_in_graph', False))
    actual_total_relations = len(relations)
    actual_valid_relations = sum(1 for r in relations if r.get('valid', False))
    actual_total_workflow = len(workflow_relations)
    actual_valid_workflow = sum(1 for w in workflow_relations if w.get('valid', False))

    # 对比统计字段
    if stats.get('total_concepts') != actual_total_concepts:
        errors.append(f"total_concepts mismatch: {stats.get('total_concepts')} vs {actual_total_concepts}")
    if stats.get('positive_concepts') != actual_positive_concepts:
        errors.append(f"positive_concepts mismatch: {stats.get('positive_concepts')} vs {actual_positive_concepts}")
    if stats.get('negative_concepts') != actual_negative_concepts:
        errors.append(f"negative_concepts mismatch: {stats.get('negative_concepts')} vs {actual_negative_concepts}")
    if stats.get('total_relations') != actual_total_relations:
        errors.append(f"total_relations mismatch: {stats.get('total_relations')} vs {actual_total_relations}")
    if stats.get('valid_relations') != actual_valid_relations:
        errors.append(f"valid_relations mismatch: {stats.get('valid_relations')} vs {actual_valid_relations}")
    if stats.get('total_workflow_relations') != actual_total_workflow:
        errors.append(f"total_workflow_relations mismatch: {stats.get('total_workflow_relations')} vs {actual_total_workflow}")
    if stats.get('valid_workflow_relations') != actual_valid_workflow:
        errors.append(f"valid_workflow_relations mismatch: {stats.get('valid_workflow_relations')} vs {actual_valid_workflow}")

    # 2. 验证Workflow Step格式
    for concept in concepts:
        if concept.get('expected_anchor') == 'Task':
            label = concept.get('label', '')
            # 验证label是否是正确的步骤编号格式
            if label and not (label.startswith('T') and all(c.isdigit() for c in label[1:] if c)):
                errors.append(f"Task concept label should be 'T<n>' format: {label}")

    # 3. 验证workflow_relation_ground_truth的family字段
    for wr in workflow_relations:
        family = wr.get('family', '')
        head = wr.get('head', '')
        if head.startswith('T') and family != 'action_object':
            errors.append(f"workflow_relation should use 'action_object' family: {head} -> {wr.get('tail')}")

    # 4. 验证workflow_relation的tail是否在concept_ground_truth中存在
    concept_labels = {c.get('label') for c in concepts}
    for wr in workflow_relations:
        tail = wr.get('tail', '')
        if tail and tail not in concept_labels:
            errors.append(f"workflow_relation tail not in concepts: {tail}")

    return {
        'file': file_path.name,
        'domain': data.get('domain_id'),
        'doc_id': data.get('documents', [{}])[0].get('doc_id'),
        'errors': errors,
        'stats': {
            'concepts': actual_total_concepts,
            'positive': actual_positive_concepts,
            'relations': actual_total_relations,
            'workflow_relations': actual_total_workflow
        }
    }

def main():
    gt_dir = Path('D:/crossextend_kg/data/ground_truth')
    results = []

    # 检查所有gold文件
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
            result = validate_ground_truth_file(file_path)
            results.append(result)
            status = 'OK' if not result['errors'] else 'ERR'
            print(f"{status} {gold_file}: {result['stats']}")
            if result['errors']:
                for err in result['errors']:
                    print(f"  - {err}")
        else:
            print(f"ERR {gold_file}: file not found")

    # 总结
    total_errors = sum(len(r['errors']) for r in results)
    print(f"\n总计: {len(results)} 文件, {total_errors} 错误")

    return results

if __name__ == '__main__':
    main()