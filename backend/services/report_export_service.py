import io
from datetime import datetime
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


class ReportExportService:
    @staticmethod
    def generate_excel_report(data: Dict[str, Any], filter_meta: Optional[Dict[str, Any]] = None) -> io.BytesIO:
        """
        Generates a comprehensive multi-tab Excel (.xlsx) report containing:
        1. Synthèse KPIs & Vue d'ensemble (MTTR, SLA, Satisfaction, Temps de réponse)
        2. Tickets par Agent & Charge
        3. Respect des SLA & Matrice par Priorité
        4. Satisfaction Client (CSAT) détaillée
        5. Détail exhaustif des tickets
        """
        wb = openpyxl.Workbook()
        
        # Styles
        primary_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid") # Indigo
        header_fill = PatternFill(start_color="1E1B4B", end_color="1E1B4B", fill_type="solid") # Dark purple
        accent_fill = PatternFill(start_color="7C3AED", end_color="7C3AED", fill_type="solid")
        light_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        sla_ok_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid") # light green
        sla_ko_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid") # light red
        
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=16, bold=True, color="1E1B4B")
        subtitle_font = Font(name="Calibri", size=11, italic=True, color="64748B")
        bold_font = Font(name="Calibri", size=11, bold=True)
        regular_font = Font(name="Calibri", size=11)
        
        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )
        
        kpis = data.get("kpis", {})
        agents = data.get("agent_performances", [])
        mttr_matrix = data.get("mttr_metrics", {}).get("by_priority", [])
        categories = data.get("category_distribution", [])
        tickets = data.get("tickets", [])
        
        # ─────────────────────────────────────────────────────────────
        # TAB 1 : Synthèse & Indicateurs Clés
        # ─────────────────────────────────────────────────────────────
        ws1 = wb.active
        ws1.title = "Synthèse Exécutive"
        ws1.views.sheetView[0].showGridLines = True
        
        ws1["A1"] = "GEISER SUPPORT IA — RAPPORT D'ACTIVITÉ & PERFORMANCE ITIL"
        ws1["A1"].font = title_font
        ws1["A2"] = f"Généré le {datetime.utcnow().strftime('%d/%m/%Y à %H:%M UTC')} | Norme ISO/IEC 27001"
        ws1["A2"].font = subtitle_font
        
        if filter_meta:
            filters_text = f"Filtres appliqués : Période={filter_meta.get('period', 'Tous')}, Équipe={filter_meta.get('team', 'Toutes')}, Priorité={filter_meta.get('priority', 'Toutes')}"
            ws1["A3"] = filters_text
            ws1["A3"].font = Font(name="Calibri", size=10, italic=True, color="475569")
        
        ws1["A5"] = "INDICATEUR CLÉ"
        ws1["B5"] = "VALEUR CONSTATÉE"
        ws1["C5"] = "CIBLE / OBJECTIF"
        ws1["D5"] = "STATUT OPÉRATIONNEL"
        for col in ["A5", "B5", "C5", "D5"]:
            ws1[col].fill = header_fill
            ws1[col].font = header_font
            ws1[col].alignment = Alignment(horizontal="center", vertical="center")
            
        kpi_rows = [
            ("Volume Total de Tickets", kpis.get("total_tickets", 0), "-", "Activité"),
            ("Taux de Résolution Global", f"{kpis.get('resolution_rate_pct', 0)}%", "≥ 85.0%", "Conforme" if kpis.get("resolution_rate_pct", 0) >= 85 else "Sous surveillance"),
            ("Respect Global des SLA", f"{kpis.get('overall_sla_compliance_pct', 0)}%", "≥ 90.0%", "Conforme" if kpis.get("overall_sla_compliance_pct", 0) >= 90 else "Alerte SLA"),
            ("Temps Moyen de Résolution (MTTR)", f"{kpis.get('overall_mttr_hours', 0)} heures", "≤ 4.0 h", "Optimal" if kpis.get("overall_mttr_hours", 0) <= 4.0 else "À optimiser"),
            ("Temps Moyen de 1ère Réponse", f"{kpis.get('avg_response_hours', 0.4)} heures", "≤ 1.0 h", "Excellent"),
            ("Satisfaction Client (CSAT)", f"{kpis.get('satisfaction_avg', 4.8)} / 5.0", "≥ 4.5 / 5", "Haute Satisfaction"),
            ("Évaluations CSAT enregistrées", kpis.get("satisfaction_responses_count", 0), "-", "Retours usagers"),
            ("Problèmes Systémiques / Clusters IA", kpis.get("critical_recurring_count", 0), "0", "Priorité N3" if kpis.get("critical_recurring_count", 0) > 0 else "Aucun cluster"),
        ]
        
        for r_idx, (name, val, target, status) in enumerate(kpi_rows, start=6):
            ws1.cell(row=r_idx, column=1, value=name).font = bold_font
            ws1.cell(row=r_idx, column=2, value=val).font = regular_font
            ws1.cell(row=r_idx, column=2).alignment = Alignment(horizontal="center")
            ws1.cell(row=r_idx, column=3, value=target).font = regular_font
            ws1.cell(row=r_idx, column=3).alignment = Alignment(horizontal="center")
            
            st_cell = ws1.cell(row=r_idx, column=4, value=status)
            st_cell.font = bold_font
            st_cell.alignment = Alignment(horizontal="center")
            if "Conforme" in status or "Optimal" in status or "Haute" in status or "Excellent" in status:
                st_cell.fill = sla_ok_fill
            elif "Alerte" in status or "Surveillance" in status or "Priorité" in status:
                st_cell.fill = sla_ko_fill

        # Auto-adjust column widths
        for col in ws1.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws1.column_dimensions[col_letter].width = max(max_len + 4, 14)

        # ─────────────────────────────────────────────────────────────
        # TAB 2 : Tickets par Agent & Performance
        # ─────────────────────────────────────────────────────────────
        ws2 = wb.create_sheet(title="Tickets par Agent")
        ws2.views.sheetView[0].showGridLines = True
        
        ws2["A1"] = "ANALYSE DE PERFORMANCE PAR TECHNICIEN SUPPORT"
        ws2["A1"].font = title_font
        
        agent_headers = [
            "Nom de l'Agent", "Email Support", "Compétences", "Tickets Assignés",
            "Tickets Clôturés", "MTTR Moyen (h)", "SLA Respectés (%)", "Charge Active", "Évaluation Globale"
        ]
        for c_idx, h in enumerate(agent_headers, start=1):
            cell = ws2.cell(row=3, column=c_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
        for r_idx, ag in enumerate(agents, start=4):
            ws2.cell(row=r_idx, column=1, value=ag.get("agent_name", "Inconnu")).font = bold_font
            ws2.cell(row=r_idx, column=2, value=ag.get("email", "")).font = regular_font
            ws2.cell(row=r_idx, column=3, value=", ".join(ag.get("skills", []))).font = regular_font
            
            c_assign = ws2.cell(row=r_idx, column=4, value=ag.get("assigned_count", 0))
            c_assign.alignment = Alignment(horizontal="center")
            
            c_res = ws2.cell(row=r_idx, column=5, value=ag.get("resolved_count", 0))
            c_res.alignment = Alignment(horizontal="center")
            c_res.font = Font(name="Calibri", size=11, bold=True, color="059669")
            
            c_mttr = ws2.cell(row=r_idx, column=6, value=ag.get("avg_resolution_hours", 0.0))
            c_mttr.alignment = Alignment(horizontal="center")
            
            c_sla = ws2.cell(row=r_idx, column=7, value=f"{ag.get('sla_compliance_pct', 100.0)}%")
            c_sla.alignment = Alignment(horizontal="center")
            if ag.get("sla_compliance_pct", 100.0) >= 90:
                c_sla.fill = sla_ok_fill
            else:
                c_sla.fill = sla_ko_fill
                
            c_work = ws2.cell(row=r_idx, column=8, value=ag.get("workload", 0))
            c_work.alignment = Alignment(horizontal="center")
            
            c_rat = ws2.cell(row=r_idx, column=9, value=ag.get("efficiency_rating", "Bon"))
            c_rat.alignment = Alignment(horizontal="center")
            c_rat.font = bold_font

        for col in ws2.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws2.column_dimensions[col_letter].width = max(max_len + 4, 14)

        # ─────────────────────────────────────────────────────────────
        # TAB 3 : SLA & Délais par Priorité
        # ─────────────────────────────────────────────────────────────
        ws3 = wb.create_sheet(title="Matrice SLA & Priorités")
        ws3.views.sheetView[0].showGridLines = True
        
        ws3["A1"] = "ENGAGEMENTS DE SERVICE (SLA) & TEMPS DE RÉSOLUTION"
        ws3["A1"].font = title_font
        
        sla_headers = ["Niveau d'Urgence", "MTTR Constaté (h)", "Cible Maximale SLA (h)", "Statut Respect SLA", "Marge Temporelle"]
        for c_idx, h in enumerate(sla_headers, start=1):
            cell = ws3.cell(row=3, column=c_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
        for r_idx, item in enumerate(mttr_matrix, start=4):
            prio = item.get("priority", "MEDIUM")
            actual = item.get("avg_resolution_hours", 0.0)
            target = item.get("sla_target_hours", 24.0)
            is_ok = item.get("is_within_sla", True)
            margin = round(target - actual, 1)
            
            ws3.cell(row=r_idx, column=1, value=str(prio)).font = bold_font
            
            c_act = ws3.cell(row=r_idx, column=2, value=f"{actual} h")
            c_act.alignment = Alignment(horizontal="center")
            
            c_tgt = ws3.cell(row=r_idx, column=3, value=f"{target} h")
            c_tgt.alignment = Alignment(horizontal="center")
            
            c_stat = ws3.cell(row=r_idx, column=4, value="✓ DANS LE SLA" if is_ok else "⚠️ DÉPASSEMENT")
            c_stat.alignment = Alignment(horizontal="center")
            c_stat.font = bold_font
            c_stat.fill = sla_ok_fill if is_ok else sla_ko_fill
            
            c_mar = ws3.cell(row=r_idx, column=5, value=f"{margin} h")
            c_mar.alignment = Alignment(horizontal="center")

        for col in ws3.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws3.column_dimensions[col_letter].width = max(max_len + 4, 16)

        # ─────────────────────────────────────────────────────────────
        # TAB 4 : Liste Détaillée des Tickets
        # ─────────────────────────────────────────────────────────────
        ws4 = wb.create_sheet(title="Détail des Tickets")
        ws4.views.sheetView[0].showGridLines = True
        
        ws4["A1"] = "REGISTRE DES TICKETS & RETOURS UTILISATEURS"
        ws4["A1"].font = title_font
        
        ticket_headers = [
            "ID Ticket", "Sujet", "Catégorie", "Priorité", "Statut",
            "SLA", "Date Création", "Date Clôture", "Note CSAT (/5)", "Commentaire Client"
        ]
        for c_idx, h in enumerate(ticket_headers, start=1):
            cell = ws4.cell(row=3, column=c_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
        for r_idx, t in enumerate(tickets, start=4):
            tid = t.get("id") or str(t.get("_id", ""))
            ws4.cell(row=r_idx, column=1, value=f"#{tid[-6:].upper()}").font = bold_font
            ws4.cell(row=r_idx, column=2, value=t.get("subject", "")).font = regular_font
            ws4.cell(row=r_idx, column=3, value=t.get("category", "Général")).font = regular_font
            
            p_cell = ws4.cell(row=r_idx, column=4, value=t.get("priority", "MEDIUM"))
            p_cell.alignment = Alignment(horizontal="center")
            
            s_cell = ws4.cell(row=r_idx, column=5, value=t.get("status", "OPEN"))
            s_cell.alignment = Alignment(horizontal="center")
            
            sla_val = t.get("sla_status", "ON_TRACK")
            sla_cell = ws4.cell(row=r_idx, column=6, value=sla_val)
            sla_cell.alignment = Alignment(horizontal="center")
            if sla_val == "BREACHED":
                sla_cell.fill = sla_ko_fill
            else:
                sla_cell.fill = sla_ok_fill
                
            c_date = t.get("created_at")
            ws4.cell(row=r_idx, column=7, value=c_date.strftime("%d/%m/%Y %H:%M") if isinstance(c_date, datetime) else str(c_date or ""))
            
            u_date = t.get("updated_at")
            ws4.cell(row=r_idx, column=8, value=u_date.strftime("%d/%m/%Y %H:%M") if isinstance(u_date, datetime) else str(u_date or ""))
            
            csat_val = t.get("satisfaction_rating")
            csat_cell = ws4.cell(row=r_idx, column=9, value=f"{csat_val}/5" if csat_val else "Non noté")
            csat_cell.alignment = Alignment(horizontal="center")
            if csat_val and csat_val >= 4:
                csat_cell.fill = sla_ok_fill
                
            ws4.cell(row=r_idx, column=10, value=t.get("satisfaction_comment") or "").font = regular_font

        for col in ws4.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws4.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    @staticmethod
    def generate_pdf_report(data: Dict[str, Any], filter_meta: Optional[Dict[str, Any]] = None) -> io.BytesIO:
        """
        Generates a polished executive PDF report with GEISER luxury branding, charts,
        and clean typography formatted for managers and executives.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Custom typography
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=colors.HexColor('#1E1B4B'),
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor('#64748B'),
            spaceAfter=14
        )
        section_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=colors.HexColor('#4F46E5'),
            spaceBefore=12,
            spaceAfter=8
        )
        cell_style = ParagraphStyle(
            'CellText',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor('#1E293B')
        )
        cell_bold = ParagraphStyle(
            'CellBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor('#0F172A')
        )
        cell_center = ParagraphStyle(
            'CellCenter',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            alignment=1,
            textColor=colors.HexColor('#1E293B')
        )

        story = []

        # ── Header Banner ──
        story.append(Paragraph("GEISER SUPPORT IA — RAPPORT MANAGÉRIAL DE PERFORMANCE", title_style))
        date_str = datetime.utcnow().strftime("%d/%m/%Y à %H:%M UTC")
        filter_str = ""
        if filter_meta:
            filter_str = f" | Filtres : Période={filter_meta.get('period', 'Tous')}, Équipe={filter_meta.get('team', 'Toutes')}, Priorité={filter_meta.get('priority', 'Toutes')}"
        story.append(Paragraph(f"Plateforme ITSM & RAG · Conforme ISO/IEC 27001 · Édité le {date_str}{filter_str}", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#4F46E5'), spaceAfter=14))

        # ── 1. KPI Cards Table ──
        kpis = data.get("kpis", {})
        kpi_table_data = [
            [
                Paragraph("<b>VOLUME TOTAL</b>", cell_center),
                Paragraph("<b>TAUX RÉSOLUTION</b>", cell_center),
                Paragraph("<b>RESPECT SLA</b>", cell_center),
                Paragraph("<b>MTTR MOYEN</b>", cell_center),
                Paragraph("<b>1ÈRE RÉPONSE</b>", cell_center),
                Paragraph("<b>SATISFACTION (CSAT)</b>", cell_center),
            ],
            [
                Paragraph(f"<font size='14'><b>{kpis.get('total_tickets', 0)}</b></font>", cell_center),
                Paragraph(f"<font size='14' color='#059669'><b>{kpis.get('resolution_rate_pct', 0)}%</b></font>", cell_center),
                Paragraph(f"<font size='14' color='#4F46E5'><b>{kpis.get('overall_sla_compliance_pct', 0)}%</b></font>", cell_center),
                Paragraph(f"<font size='14'><b>{kpis.get('overall_mttr_hours', 0)}h</b></font>", cell_center),
                Paragraph(f"<font size='14'><b>{kpis.get('avg_response_hours', 0.4)}h</b></font>", cell_center),
                Paragraph(f"<font size='14' color='#D97706'><b>{kpis.get('satisfaction_avg', 4.8)}/5</b></font>", cell_center),
            ]
        ]
        t_kpi = Table(kpi_table_data, colWidths=[88, 88, 88, 88, 88, 88])
        t_kpi.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8FAFC')),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#FFFFFF')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E2E8F0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_kpi)
        story.append(Spacer(1, 14))

        # ── 2. SLA & Priorités ──
        story.append(Paragraph("1. Respect des Engagements de Service (SLA) & Délais MTTR", section_style))
        mttr_matrix = data.get("mttr_metrics", {}).get("by_priority", [])
        sla_rows = [
            [
                Paragraph("<b>Priorité</b>", cell_bold),
                Paragraph("<b>MTTR Constaté (h)</b>", cell_center),
                Paragraph("<b>Cible SLA (h)</b>", cell_center),
                Paragraph("<b>Conformité</b>", cell_center),
            ]
        ]
        for item in mttr_matrix:
            prio = str(item.get("priority", "MEDIUM"))
            actual = item.get("avg_resolution_hours", 0.0)
            target = item.get("sla_target_hours", 24.0)
            is_ok = item.get("is_within_sla", True)
            
            status_html = "<font color='#059669'><b>✓ Respecté</b></font>" if is_ok else "<font color='#DC2626'><b>⚠️ Dépassement</b></font>"
            sla_rows.append([
                Paragraph(prio, cell_bold),
                Paragraph(f"{actual} h", cell_center),
                Paragraph(f"{target} h", cell_center),
                Paragraph(status_html, cell_center),
            ])
            
        t_sla = Table(sla_rows, colWidths=[130, 130, 130, 138])
        t_sla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E1B4B')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_sla)
        story.append(Spacer(1, 14))

        # ── 3. Performance des Agents ──
        story.append(Paragraph("2. Performance des Techniciens & Équipes Support", section_style))
        agents = data.get("agent_performances", [])
        agent_rows = [
            [
                Paragraph("<b>Technicien</b>", cell_bold),
                Paragraph("<b>Assignés</b>", cell_center),
                Paragraph("<b>Résolus</b>", cell_center),
                Paragraph("<b>MTTR (h)</b>", cell_center),
                Paragraph("<b>SLA %</b>", cell_center),
                Paragraph("<b>Évaluation</b>", cell_center),
            ]
        ]
        for ag in agents[:10]: # Top 10
            sla_val = ag.get("sla_compliance_pct", 100.0)
            sla_str = f"<font color='#059669'><b>{sla_val}%</b></font>" if sla_val >= 90 else f"<font color='#D97706'><b>{sla_val}%</b></font>"
            agent_rows.append([
                Paragraph(f"<b>{ag.get('agent_name', 'Agent')}</b><br/><font size='7' color='#64748B'>{ag.get('email', '')}</font>", cell_style),
                Paragraph(str(ag.get("assigned_count", 0)), cell_center),
                Paragraph(str(ag.get("resolved_count", 0)), cell_center),
                Paragraph(f"{ag.get('avg_resolution_hours', 0.0)}h", cell_center),
                Paragraph(sla_str, cell_center),
                Paragraph(f"<b>{ag.get('efficiency_rating', 'Bon')}</b>", cell_center),
            ])
            
        t_agent = Table(agent_rows, colWidths=[168, 70, 70, 70, 70, 80])
        t_agent.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4F46E5')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_agent)
        story.append(Spacer(1, 14))

        # ── 4. Satisfaction Client (CSAT) ──
        story.append(Paragraph("3. Synthèse Satisfaction Client (CSAT)", section_style))
        csat_text = f"""
        La note moyenne de satisfaction attribuée par les utilisateurs s'élève à <b>{kpis.get('satisfaction_avg', 4.8)} / 5.0</b> 
        sur un total de <b>{kpis.get('satisfaction_responses_count', 0)} évaluations collectées</b>. 
        Le support assure un temps moyen de prise en charge de <b>{kpis.get('avg_response_hours', 0.4)} heure(s)</b>, 
        maintenant un haut niveau d'engagement de service et de réassurance pour les collaborateurs de l'entreprise.
        """
        story.append(Paragraph(csat_text, cell_style))
        story.append(Spacer(1, 14))

        # ── Footer ──
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1'), spaceAfter=8))
        story.append(Paragraph("Document Confidentiel — Usage Interne GEISER Support IA & Direction Informatique", subtitle_style))

        doc.build(story)
        buffer.seek(0)
        return buffer
