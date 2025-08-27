#!/usr/bin/env python3
"""
이슈별 레포트 생성 스크립트

각 클러스터(이슈)에 대해 완전한 레포트를 생성하여 블로그에 올릴 수 있는 형태로 만듭니다.
- Issues 테이블의 모든 정보
- Common Points
- Bias Summaries
- Media Summaries
- 편향성 퍼센트는 HTML 게이지바로 시각화
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

# utils 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.supabase_manager_unified import UnifiedSupabaseManager


class IssueReportGenerator:
    def __init__(self):
        self.sm = UnifiedSupabaseManager()
        
    def generate_all_issue_reports(self):
        """모든 이슈에 대해 레포트를 생성합니다."""
        print("🚀 이슈별 레포트 생성 시작")
        print("=" * 60)
        
        try:
            # 모든 테이블에서 데이터 로드
            issues_result = self.sm.client.table('issues').select('*').gt('id', 1).execute()
            common_points_result = self.sm.client.table('common_points').select('*').execute()
            bias_summaries_result = self.sm.client.table('bias_summaries').select('*').execute()
            media_summaries_result = self.sm.client.table('media_summaries').select('*').execute()
            media_outlets_result = self.sm.client.table('media_outlets').select('*').execute()
            
            if not issues_result.data:
                print("❌ 이슈 데이터를 찾을 수 없습니다.")
                return
            
            issues = issues_result.data
            common_points = common_points_result.data
            bias_summaries = bias_summaries_result.data
            media_summaries = media_summaries_result.data
            media_outlets = media_outlets_result.data
            
            # 언론사 ID를 이름으로 매핑
            media_id_to_name = {media['id']: media['name'] for media in media_outlets}
            
            print(f"📊 {len(issues)}개 이슈, {len(common_points)}개 공통점, {len(bias_summaries)}개 편향성 요약, {len(media_summaries)}개 언론사 요약 로드 완료\n")
            
            # 각 이슈별로 레포트 생성
            all_reports = []
            
            for issue in issues:
                issue_id = issue['id']
                print(f"📊 이슈 {issue_id} 레포트 생성 중...")
                
                # 해당 이슈의 관련 데이터 수집
                issue_common_points = [cp for cp in common_points if cp['issue_id'] == issue_id]
                issue_bias_summaries = [bs for bs in bias_summaries if bs['issue_id'] == issue_id]
                issue_media_summaries = [ms for ms in media_summaries if ms['issue_id'] == issue_id]
                
                # 레포트 생성
                report = self._create_issue_report(
                    issue, 
                    issue_common_points, 
                    issue_bias_summaries, 
                    issue_media_summaries,
                    media_id_to_name
                )
                
                all_reports.append(report)
                print(f"   ✅ 이슈 {issue_id} 레포트 생성 완료")
            
            # 전체 레포트를 JSON으로 저장
            self._save_reports_to_json(all_reports)
            
            # HTML 형태로도 저장 (블로그용)
            self._save_reports_to_html(all_reports)
            
            print("\n✅ 모든 이슈 레포트 생성 완료!")
            print("🎉 JSON과 HTML 형태로 저장되었습니다!")
            
        except Exception as e:
            print(f"❌ 레포트 생성 중 오류 발생: {e}")
    
    def _create_issue_report(self, issue: Dict, common_points: List[Dict], 
                            bias_summaries: List[Dict], media_summaries: List[Dict],
                            media_id_to_name: Dict[int, str]) -> Dict:
        """개별 이슈 레포트를 생성합니다."""
        report = {
            'issue_id': issue['id'],
            'title': issue.get('title', '제목 없음'),
            'subtitle': issue.get('subtitle', '부제목 없음'),
            'summary': issue.get('summary', '요약 없음'),
            'dominant_bias': issue.get('dominant_bias', '알 수 없음'),
            'source_count': issue.get('source_count', 0),
            'created_at': issue.get('created_at', ''),
            'updated_at': issue.get('updated_at', ''),
            'eli5': issue.get('eli5', 'ELI5 설명 없음'),
            
            # 편향성 퍼센트 (게이지바용)
            'bias_percentages': {
                'left': issue.get('bias_left_pct', 0),
                'center': issue.get('bias_center_pct', 0),
                'right': issue.get('bias_right_pct', 0)
            },
            
            # Common Points
            'common_points': {
                'main_topics': [],
                'common_keywords': [],
                'core_issues': [],
                'political_context': '',
                'media_bias_patterns': ''
            },
            
            # Bias Summaries
            'bias_summaries': {
                'left': '',
                'center': '',
                'right': ''
            },
            
            # Media Summaries
            'media_summaries': []
        }
        
        # Common Points 정리
        for cp in common_points:
            point = cp['point']
            if '주요 주제:' in point:
                topic = point.replace('주요 주제:', '').strip()
                if topic not in report['common_points']['main_topics']:
                    report['common_points']['main_topics'].append(topic)
            elif '공통 키워드:' in point:
                keyword = point.replace('공통 키워드:', '').strip()
                if keyword not in report['common_points']['common_keywords']:
                    report['common_points']['common_keywords'].append(keyword)
            elif '핵심 이슈:' in point:
                core_issue = point.replace('핵심 이슈:', '').strip()
                if core_issue not in report['common_points']['core_issues']:
                    report['common_points']['core_issues'].append(core_issue)
            elif '정치적 맥락:' in point:
                report['common_points']['political_context'] = point.replace('정치적 맥락:', '').strip()
            elif '언론사 편향성:' in point:
                report['common_points']['media_bias_patterns'] = point.replace('언론사 편향성:', '').strip()
        
        # Bias Summaries 정리
        for bs in bias_summaries:
            bias_type = bs['bias'].lower()
            if bias_type in report['bias_summaries']:
                report['bias_summaries'][bias_type] = bs['summary']
        
        # Media Summaries 정리
        for ms in media_summaries:
            media_name = media_id_to_name.get(ms['media_id'], f"언론사_{ms['media_id']}")
            report['media_summaries'].append({
                'media_name': media_name,
                'media_id': ms['media_id'],
                'summary': ms['summary']
            })
        
        return report
    
    def _save_reports_to_json(self, reports: List[Dict]):
        """레포트를 JSON 파일로 저장합니다."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 전체 레포트
        all_reports_file = f"outputs/issue_reports_{timestamp}.json"
        with open(all_reports_file, 'w', encoding='utf-8') as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)
        
        # 최신 레포트
        latest_file = "outputs/issue_reports_latest.json"
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)
        
        print(f"📁 JSON 파일 저장 완료:")
        print(f"   - 전체: {all_reports_file}")
        print(f"   - 최신: {latest_file}")
    
    def _save_reports_to_html(self, reports: List[Dict]):
        """레포트를 HTML 파일로 저장합니다 (블로그용)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 전체 레포트 HTML
        all_reports_html = f"outputs/issue_reports_{timestamp}.html"
        with open(all_reports_html, 'w', encoding='utf-8') as f:
            f.write(self._generate_html_content(reports))
        
        # 최신 레포트 HTML
        latest_html = "outputs/issue_reports_latest.html"
        with open(latest_html, 'w', encoding='utf-8') as f:
            f.write(self._generate_html_content(reports))
        
        print(f"📁 HTML 파일 저장 완료:")
        print(f"   - 전체: {all_reports_html}")
        print(f"   - 최신: {latest_html}")
    
    def _generate_html_content(self, reports: List[Dict]) -> str:
        """HTML 콘텐츠를 생성합니다."""
        html_content = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>뉴스 이슈 분석 레포트</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .issue-card {
            border: 2px solid #ecf0f1;
            border-radius: 15px;
            margin-bottom: 40px;
            padding: 25px;
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        }
        .issue-header {
            background: linear-gradient(135deg, #3498db, #2980b9);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin: -25px -25px 25px -25px;
        }
        .issue-title {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .issue-subtitle {
            font-size: 18px;
            opacity: 0.9;
            margin-bottom: 15px;
        }
        .issue-summary {
            font-size: 16px;
            line-height: 1.8;
        }
        .bias-gauge {
            background: #ecf0f1;
            border-radius: 20px;
            height: 30px;
            margin: 20px 0;
            position: relative;
            overflow: hidden;
        }
        .bias-left {
            background: linear-gradient(90deg, #3498db, #2980b9);
            height: 100%;
            float: left;
            transition: width 0.5s ease;
        }
        .bias-center {
            background: linear-gradient(90deg, #ecf0f1, #bdc3c7);
            height: 100%;
            float: left;
            transition: width 0.5s ease;
        }
        .bias-right {
            background: linear-gradient(90deg, #e74c3c, #c0392b);
            height: 100%;
            float: left;
            transition: width 0.5s ease;
        }
        .bias-labels {
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
            font-size: 14px;
        }
        .bias-left-label {
            color: #2980b9;
            font-weight: bold;
        }
        .bias-center-label {
            color: #7f8c8d;
            font-weight: bold;
        }
        .bias-right-label {
            color: #c0392b;
            font-weight: bold;
        }
        .section {
            margin: 25px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            border-left: 4px solid #3498db;
        }
        .section-title {
            font-size: 20px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 15px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .point-item {
            background: white;
            padding: 15px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 3px solid #3498db;
        }
        .bias-left-item {
            border-left-color: #3498db;
            background: linear-gradient(135deg, #ebf3fd 0%, #ffffff 100%);
        }
        .bias-center-item {
            border-left-color: #95a5a6;
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        }
        .bias-right-item {
            border-left-color: #e74c3c;
            background: linear-gradient(135deg, #fdf2f2 0%, #ffffff 100%);
        }
        .eli5-content {
            background: linear-gradient(135deg, #fff8e1 0%, #ffffff 100%);
            border-left-color: #f39c12;
            font-size: 15px;
            line-height: 1.8;
        }
        .media-item {
            background: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 10px;
            border: 1px solid #ecf0f1;
            transition: all 0.3s ease;
        }
        .media-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .media-left {
            border-left: 4px solid #3498db;
            background: linear-gradient(135deg, #ebf3fd 0%, #ffffff 100%);
        }
        .media-center {
            border-left: 4px solid #95a5a6;
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        }
        .media-right {
            border-left: 4px solid #e74c3c;
            background: linear-gradient(135deg, #fdf2f2 0%, #ffffff 100%);
        }
        .media-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #ecf0f1;
        }
        .media-name {
            font-weight: bold;
            color: #2c3e50;
            font-size: 18px;
        }
        .media-bias {
            font-size: 14px;
            font-weight: bold;
            padding: 5px 12px;
            border-radius: 20px;
            background: #f8f9fa;
        }
        .media-left .media-bias {
            background: #ebf3fd;
            color: #2980b9;
        }
        .media-center .media-bias {
            background: #f8f9fa;
            color: #7f8c8d;
        }
        .media-right .media-bias {
            background: #fdf2f2;
            color: #c0392b;
        }
        .media-summary {
            color: #34495e;
            line-height: 1.7;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .stat-item {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            border: 2px solid #ecf0f1;
        }
        .stat-number {
            font-size: 32px;
            font-weight: bold;
            color: #3498db;
        }
        .bias-left {
            color: #2980b9;
        }
        .bias-center {
            color: #7f8c8d;
        }
        .bias-right {
            color: #c0392b;
        }
        .stat-label {
            color: #7f8c8d;
            margin-top: 5px;
        }
        .timestamp {
            text-align: center;
            color: #95a5a6;
            margin-top: 30px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 뉴스 이슈 분석 레포트</h1>
        <div class="timestamp">생성 시간: """ + datetime.now().strftime("%Y년 %m월 %d일 %H:%M") + """</div>
"""
        
        for report in reports:
            html_content += self._generate_issue_html(report)
        
        html_content += """
    </div>
</body>
</html>
"""
        return html_content
    
    def _generate_issue_html(self, report: Dict) -> str:
        """개별 이슈의 HTML을 생성합니다."""
        # 편향성 게이지바 계산
        left_pct = report['bias_percentages']['left']
        center_pct = report['bias_percentages']['center']
        right_pct = report['bias_percentages']['right']
        
        html = f"""
        <div class="issue-card">
            <div class="issue-header">
                <div class="issue-title">{report['title']}</div>
                <div class="issue-subtitle">{report['subtitle']}</div>
                <div class="issue-summary">{report['summary'].replace(chr(10), '<br>')}</div>
            </div>
            
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number">{report['source_count']}</div>
                    <div class="stat-label">📊 기사 수</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number bias-{report['dominant_bias'].lower()}">{report['dominant_bias']}</div>
                    <div class="stat-label">🎯 주요 편향성</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{len(report['media_summaries'])}</div>
                    <div class="stat-label">📰 언론사 수</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">🎯 편향성 분석</div>
                <div class="bias-gauge">
                    <div class="bias-left" style="width: {left_pct}%"></div>
                    <div class="bias-center" style="width: {center_pct}%"></div>
                    <div class="bias-right" style="width: {right_pct}%"></div>
                </div>
                <div class="bias-labels">
                    <span class="bias-left-label">🔵 좌파 ({left_pct:.1f}%)</span>
                    <span class="bias-center-label">⚪ 중도 ({center_pct:.1f}%)</span>
                    <span class="bias-right-label">🔴 우파 ({right_pct:.1f}%)</span>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">🔍 공통점 분석</div>
                <div class="point-item">
                    <strong>🎯 주요 주제:</strong> {', '.join(report['common_points']['main_topics']) if report['common_points']['main_topics'] else '분석 중'}
                </div>
                <div class="point-item">
                    <strong>🔑 공통 키워드:</strong> {', '.join(report['common_points']['common_keywords']) if report['common_points']['common_keywords'] else '분석 중'}
                </div>
                <div class="point-item">
                    <strong>💡 핵심 이슈:</strong> {', '.join(report['common_points']['core_issues']) if report['common_points']['core_issues'] else '분석 중'}
                </div>
                <div class="point-item">
                    <strong>🏛️ 정치적 맥락:</strong> {report['common_points']['political_context'] if report['common_points']['political_context'] else '분석 중'}
                </div>
                <div class="point-item">
                    <strong>📺 언론사 편향성:</strong> {report['common_points']['media_bias_patterns'] if report['common_points']['media_bias_patterns'] else '분석 중'}
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">📰 편향성별 요약</div>
                <div class="point-item bias-left-item">
                    <strong>🔵 좌파 편향:</strong> {report['bias_summaries']['left'] if report['bias_summaries']['left'] else '분석 중'}
                </div>
                <div class="point-item bias-center-item">
                    <strong>⚪ 중도 편향:</strong> {report['bias_summaries']['center'] if report['bias_summaries']['center'] else '분석 중'}
                </div>
                <div class="point-item bias-right-item">
                    <strong>🔴 우파 편향:</strong> {report['bias_summaries']['right'] if report['bias_summaries']['right'] else '분석 중'}
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">🧒 5살 아이도 이해할 수 있는 설명 (ELI5)</div>
                <div class="point-item eli5-content">
                    {report['eli5'].replace(chr(10), '<br>') if report['eli5'] and report['eli5'] != 'ELI5 설명 없음' else 'ELI5 설명이 준비 중입니다.'}
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">📺 언론사별 보도 경향</div>
"""
        
        for media in report['media_summaries']:
            # 언론사 편향성에 따른 이모지와 색상 클래스 결정
            media_bias = media.get('media_bias', 'center').lower()
            if media_bias == 'left':
                bias_emoji = '🔵'
                bias_class = 'media-left'
            elif media_bias == 'right':
                bias_emoji = '🔴'
                bias_class = 'media-right'
            else:
                bias_emoji = '⚪'
                bias_class = 'media-center'
            
            html += f"""
                <div class="media-item {bias_class}">
                    <div class="media-header">
                        <span class="media-name">{media['media_name']}</span>
                        <span class="media-bias">{bias_emoji} {media.get('media_bias', 'Center')}</span>
                    </div>
                    <div class="media-summary">{media['summary']}</div>
                </div>
"""
        
        html += """
            </div>
        </div>
"""
        return html


def main():
    """메인 함수"""
    try:
        generator = IssueReportGenerator()
        generator.generate_all_issue_reports()
    except Exception as e:
        print(f"❌ 메인 실행 중 오류 발생: {e}")


if __name__ == "__main__":
    main()
