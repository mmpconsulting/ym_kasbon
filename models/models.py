# -*- coding: utf-8 -*-

from num2words import num2words
from odoo import api, Command, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html2plaintext


from odoo.osv import expression
from odoo.tools.float_utils import float_is_zero
from bisect import bisect_left
from collections import defaultdict
import re

class AccountMove(models.Model):
    _inherit = 'account.move'
    _description = 'Account Move'
    
    lpj_kasbon_operasional_id = fields.Many2one('lpj.kasbon.operasional', string='LPJ Kasbon Operasional', compute='_compute_reference')
    kasbon_operasional_id = fields.Many2one('kasbon.operasional', string='Kasbon Operasional', compute='_compute_reference')
    cek_bg_no = fields.Char('Cek/BG No.')
    is_kasbon = fields.Boolean(compute='_compute_is_kasbon', string='Is Kasbon')
    terbilang = fields.Char('Terbilang', compute='amount_to_words')
    dibayarkan_kpd_id = fields.Many2one('hr.employee', string='Dibayarkan Kepada')
    lampiran = fields.Char('Lampiran')
    analytic_distribution = fields.Json(string='Proyek')
    analytic_precision = fields.Integer(string='Analytic Precision', store=False, default=lambda self: self.env['decimal.precision'].precision_get("Percentage Analytic"))
    analytic_distribution_convert_to_char = fields.Char('Analytic Distribution Convert to Char', compute='_compute_convert_chart')
    
    @api.depends('analytic_distribution')
    def _compute_convert_chart(self):
        for record in self:
            analytic_distribution = ''
            if record.analytic_distribution:
                distibution_ids = []
                for distibution in list(record.analytic_distribution):
                    distibution_ids.append(int(distibution))
                
                anlytic = self.env['account.analytic.account'].browse(distibution_ids).mapped('name')
                if anlytic:
                    analytic_distribution = " / ".join(anlytic)
            record.analytic_distribution_convert_to_char = analytic_distribution
    
    @api.depends('journal_id', 'journal_id.is_kasbon', 'journal_id.is_lpj_kasbon' )
    def _compute_is_kasbon(self):
        for move in self:
            is_kasbon = False
            if move.journal_id:
                if move.journal_id.is_kasbon == True or move.journal_id.is_lpj_kasbon == True:
                    is_kasbon = True
            move.is_kasbon = is_kasbon

    @api.depends('line_ids', 'line_ids.credit', 'line_ids.debit')
    def amount_to_words(self):
        for move in self:
            terbilang = 0
            for line in move.line_ids:
                if move.journal_id:
                    if move.journal_id.opsi_print == 'debit':
                        if line.debit != 0.00:
                            terbilang = terbilang + line.debit
                    elif move.journal_id.opsi_print == 'credit':
                        if line.credit != 0.00:
                            terbilang = terbilang + line.credit

            move.terbilang = num2words(int(terbilang), to='currency', lang='id')
    
    
    @api.depends('ref', 'name')
    def _compute_reference(self):
        for move in self:
            lpj_kasbon_operasional_id = False
            kasbon_operasional_id = False
            lpj_kasbon_operasional = self.env['lpj.kasbon.operasional'].search(['|', ('name', '=', move.ref), ('move_id', '=', move.id)], limit=1)
            if lpj_kasbon_operasional:
                lpj_kasbon_operasional_id = lpj_kasbon_operasional.id
            kasbon_operasional = self.env['kasbon.operasional'].search(['|', ('name', '=', move.ref), ('move_id', '=', move.id)], limit=1)
            if kasbon_operasional:
                kasbon_operasional_id = kasbon_operasional.id
            move.lpj_kasbon_operasional_id = lpj_kasbon_operasional_id
            move.kasbon_operasional_id = kasbon_operasional_id


class AccountJournal(models.Model):
    _inherit = 'account.journal'
    _description = 'Account Journal'
    

    is_kasbon = fields.Boolean('Is Kasbon Operaional')
    is_lpj_kasbon = fields.Boolean('Is LPJ Kasbon Operaional')
    account_debit_kasbon_id = fields.Many2one('account.account', string='Account Debit Kasbon', ondelete='restrict')
    account_credit_kasbon_id = fields.Many2one('account.account', string='Account Credit Kasbon', ondelete='restrict')
    account_credit_lpj_kasbon_id = fields.Many2one('account.account', string='Account Credit LPJ Kasbon', ondelete='restrict')
    judul_report = fields.Char('Judul Report')
    opsi_print = fields.Selection([
        ('debit', 'Debit'),
        ('credit', 'Credit'),
    ], string='Opsi Print')

    @api.onchange('account_debit_kasbon_id')
    def _onchange_account_debit_kasbon_id(self):
        account_credit_lpj_kasbon_id = False
        if self.account_debit_kasbon_id:
            account_credit_lpj_kasbon_id = self.account_debit_kasbon_id.id
        self.account_credit_lpj_kasbon_id = account_credit_lpj_kasbon_id



class KasbonOperasional(models.Model):
    _name = 'kasbon.operasional'
    _description = 'Kasbon Operasional'

    def default_diterima(self):
        diterima = False
        if self.env.user.employee_id:
            diterima = self.env.user.employee_id.id
        return diterima
    
    def default_journal(self):
        journal = False
        journal_id = self.env['account.journal'].search([('is_kasbon', '=', True)], limit =1)
        if journal_id:
            journal = journal_id.id
        return journal
    
    def default_account_credit(self):
        account_credit_kasbon_id = False
        journal_id = self.env['account.journal'].search([('is_kasbon', '=', True)], limit =1)
        if journal_id:
            account_credit_kasbon_id = journal_id.account_credit_kasbon_id.id
        return account_credit_kasbon_id
    
    account_credit_kasbon_id = fields.Many2one('account.account', string='Akun Kas/Bank', ondelete='restrict', default=default_account_credit)
    date = fields.Date('Tanggal', default=fields.Date.today())
    name = fields.Char('Nomor', default="/", copy=False)
    bisnis_unit_id = fields.Many2one('res.company', string='Bisnis Unit', default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Departemen', default=lambda self: self.env.user.department_id)
    analytic_id = fields.Many2one('account.analytic.account', string='Proyek')
    analytic_distribution = fields.Json(string='Proyek')
    analytic_precision = fields.Integer(string='Analytic Precision', store=False, default=lambda self: self.env['decimal.precision'].precision_get("Percentage Analytic"))
    kasbon_operasional_ids = fields.One2many('kasbon.operasional.line', 'kasbon_id', string='Kasbon Operasional Line')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submission', 'Submission'),
        ('approved_1', 'Approved 1'),
        ('approved_2', 'Approved 2'),
        ('done', 'Done'),
        ('not_approved', 'Not Approved'),
    ], string='state', default="draft")
    analytic_distribution_convert_to_char = fields.Char('Analytic Distribution Convert to Char', compute='_compute_convert_chart')
    
    company_id = fields.Many2one('res.company', string='Bisnis Unit', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Curenncy', compute='_compute_currency_id', store=True)
    journal_id = fields.Many2one('account.journal', string='Journal', default=default_journal, domain=[('is_kasbon', '=', True)], ondelete='restrict')
    move_id = fields.Many2one('account.move', string='Joutnal Entries', ondelete='restrict')
    
    terbilang = fields.Char('Terbilang :', compute="amount_to_words", readonly=True)
    note = fields.Text('Note')
    total = fields.Float('Total :', compute="amount_to_words", readonly=True, store=True)

    diketahui_id = fields.Many2one('hr.employee', string='Diketahui oleh')
    disetujui_id = fields.Many2one('hr.employee', string='Disetujui oleh')
    diserahkan_id = fields.Many2one('hr.employee', string='Diserahkan oleh', default=default_diterima)
    diterima_id = fields.Many2one('hr.employee', string='Diterima oleh', default=default_diterima)

    @api.depends('analytic_distribution')
    def _compute_convert_chart(self):
        for record in self:
            analytic_distribution = ''
            if record.analytic_distribution:
                distibution_ids = []
                for distibution in list(record.analytic_distribution):
                    distibution_ids.append(int(distibution))
                
                anlytic = self.env['account.analytic.account'].browse(distibution_ids).mapped('name')
                if anlytic:
                    analytic_distribution = " / ".join(anlytic)
            record.analytic_distribution_convert_to_char = analytic_distribution


    @api.depends('journal_id.currency_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.journal_id.currency_id or rec.company_id.currency_id

    @api.depends('kasbon_operasional_ids', 'kasbon_operasional_ids.jumlah')
    def amount_to_words(self):
        for rec in self:
            total = sum([x.jumlah for x in rec.kasbon_operasional_ids])
            rec.terbilang = num2words(int(total), to='currency', lang='id')
            rec.total = total

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].next_by_code('kasbon.operasional')
        res = super(KasbonOperasional, self).create(vals_list)
        return res
    
    def set_to_submission(self):
        self.write({'state': 'submission'})

    def set_to_approved_1(self):
        self.write({'state': 'approved_1'})


    def set_to_approved_2(self):
        self.write({'state': 'approved_2'})

    def set_to_done(self):
        self.write({'state': 'done'})
        create_journal_entries = self.env['account.move'].create({
            'ref': self.name,
            'journal_id': self.journal_id.id,
            'move_type': 'entry',
        })
        if create_journal_entries:
            res = [(0,0, {
                'account_id': self.journal_id.account_debit_kasbon_id.id,
                'currency_id': self.currency_id.id,
                'name': "Kasbon %s %s - %s - %s" % (self.currency_id.symbol, str(self.total), self.diterima_id.name, str(self.date)),
                'analytic_distribution': self.analytic_distribution,
                'debit': self.total,
                'credit': 0,
            }), (0,0, {
                'account_id': self.account_credit_kasbon_id.id,
                'currency_id': self.currency_id.id,
                'name': "Kasbon %s %s - %s - %s" % (self.currency_id.symbol, str(self.total), self.diterima_id.name, str(self.date)),
                'analytic_distribution': self.analytic_distribution,
                'debit': 0,
                'credit': self.total,
            })]
            create_journal_entries.write({'line_ids': res})
            self.move_id = create_journal_entries.id
            create_journal_entries.action_post()


    def set_to_not_approved(self):
        self.write({'state': 'not_approved'})



class KasbonOperasionalLine(models.Model):
    _name = 'kasbon.operasional.line'
    _description = 'Kasbon Operasional Line'
    
    kasbon_id = fields.Many2one('kasbon.operasional', string='kasbon', ondelete='cascade')
    name = fields.Char('Uraian')
    jumlah = fields.Float('Jumlah')
    


class LpjKasbonOperasional(models.Model):
    _name = 'lpj.kasbon.operasional'
    _description = 'Lpj Kasbon Operasional'

    def default_diterima(self):
        diterima = False
        if self.env.user.employee_id:
            diterima = self.env.user.employee_id.id
        return diterima
    
    def default_journal(self):
        journal = False
        journal_id = self.env['account.journal'].search([('is_lpj_kasbon', '=', True)], limit =1)
        if journal_id:
            journal = journal_id.id
        return journal
    
    name = fields.Char('Name', default="Draft", copy=False)
    date = fields.Date('Tanggal', default=fields.Date.today())
    kasbon_id = fields.Many2one('kasbon.operasional', string='No. Kasbon', domain=[('state', '=', 'done')], ondelete='restrict')
    bisnis_unit_id = fields.Many2one('res.company', string='Bisnis Unit', default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Departemen', default=lambda self: self.env.user.department_id)
    analytic_id = fields.Many2one('account.analytic.account', string='Proyek')
    analytic_distribution = fields.Json(string='Proyek')
    analytic_precision = fields.Integer(string='Analytic Precision', store=False, default=lambda self: self.env['decimal.precision'].precision_get("Percentage Analytic"))
    lpj_line_ids = fields.One2many('lpj.kasbon.operasional.line', 'lpj_id', string='LPJ Line')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submission', 'Submission'),
        ('approved_1', 'Approved 1'),
        ('approved_2', 'Approved 2'),
        ('done', 'Done'),
        ('not_approved', 'Not Approved'),
    ], string='state', default="draft")
    analytic_distribution_convert_to_char = fields.Char('Analytic Distribution Convert to Char', compute='_compute_convert_chart')

    note = fields.Text('Note')
    jumlah_kasbon = fields.Float('Jumlah Kasbon', related='kasbon_id.total')
    total_pertanggungjawaban = fields.Float('Total Pertanggungjawaban', readonly=True, store=True, compute="amount_to_words")
    lebih_kurang_bayar = fields.Float('Lebih/(Kurang) Bayar', readonly=True, store=True, compute="amount_to_words")

    company_id = fields.Many2one('res.company', string='Bisnis Unit', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Curenncy', compute='_compute_currency_id')
    journal_id = fields.Many2one('account.journal', string='Journal', default=default_journal, domain=[('is_lpj_kasbon', '=', True)], ondelete='restrict')
    move_id = fields.Many2one('account.move', string='Joutnal Entries', ondelete='restrict')

    diserahkan_id = fields.Many2one('hr.employee', string='Diserahkan oleh', default=default_diterima)
    diperiksa_id = fields.Many2one('hr.employee', string='Diperikasa oleh')
    disetujui_id = fields.Many2one('hr.employee', string='Disetujui oleh')
    dibukukan_id = fields.Many2one('hr.employee', string='Dibukukan oleh')

    @api.depends('analytic_distribution')
    def _compute_convert_chart(self):
        for record in self:
            analytic_distribution = ''
            if record.analytic_distribution:
                distibution_ids = []
                for distibution in list(record.analytic_distribution):
                    distibution_ids.append(int(distibution))
                
                anlytic = self.env['account.analytic.account'].browse(distibution_ids).mapped('name')
                if anlytic:
                    analytic_distribution = " / ".join(anlytic)
            record.analytic_distribution_convert_to_char = analytic_distribution
    
    @api.depends('journal_id.currency_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.journal_id.currency_id.id or rec.company_id.currency_id.id

    @api.onchange('kasbon_id')
    def _onchange_kasbon_id(self):
        if self.kasbon_id:
            bisnis_unit_id = False
            department_id = False
            analytic_id = False
            analytic_distribution = False
            analytic_precision = False
            if self.kasbon_id.bisnis_unit_id:
                bisnis_unit_id = self.kasbon_id.bisnis_unit_id.id
            if self.kasbon_id.department_id:
                department_id = self.kasbon_id.department_id.id
            if self.kasbon_id.analytic_id:
                department_id = self.kasbon_id.analytic_id.id
            if self.kasbon_id.analytic_distribution:
                analytic_distribution = self.kasbon_id.analytic_distribution
            if self.kasbon_id.analytic_precision:
                analytic_precision = self.kasbon_id.analytic_precision
            self.bisnis_unit_id = bisnis_unit_id
            self.department_id = department_id
            self.analytic_id = analytic_id
            self.analytic_distribution = analytic_distribution
            self.analytic_precision = analytic_precision

    @api.depends('lpj_line_ids', 'lpj_line_ids.jumlah')
    def amount_to_words(self):
        for rec in self:
            total = sum([x.jumlah for x in rec.lpj_line_ids])
            rec.total_pertanggungjawaban = total
            rec.lebih_kurang_bayar = rec.jumlah_kasbon - total

    def set_to_submission(self):
        self.write({'state': 'submission'})
        self.name = self.env['ir.sequence'].next_by_code('lpj.kasbon.operasional')

    def set_to_approved_1(self):
        self.write({'state': 'approved_1'})


    def set_to_approved_2(self):
        self.write({'state': 'approved_2'})

    def set_to_done(self):
        self.write({'state': 'done'})
        create_journal_entries = self.env['account.move'].create({
            'ref': self.name,
            'journal_id': self.journal_id.id,
            'move_type': 'entry',
        })
        if create_journal_entries:
            lines = []
            for rec in self.lpj_line_ids:
                lines.append((0, 0, {
                    'account_id': rec.account_id.id,
                    'currency_id': rec.currency_id.id,
                    'name': "LPJ Kasbon %s %s %s - %s - %s" % (rec.ket, rec.currency_id.symbol, str(rec.jumlah), rec.diserahkan_id.name, str(rec.date)),
                    'analytic_distribution': self.analytic_distribution,
                    'debit': rec.jumlah,
                    'credit': 0,
                }))
            lines.append((0, 0, {
                'account_id': self.journal_id.account_credit_lpj_kasbon_id.id,
                'currency_id': self.currency_id.id,
                'name': "LPJ Kasbon Operasional %s %s - %s - %s" % (self.currency_id.symbol, str(self.total_pertanggungjawaban), self.diserahkan_id.name, str(self.date)),
                'analytic_distribution': self.analytic_distribution,
                'debit': 0,
                'credit': self.total_pertanggungjawaban,
            }))
            print("=========", lines)
            create_journal_entries.write({'line_ids': lines})
            self.move_id = create_journal_entries.id
            create_journal_entries.action_post()


    def set_to_not_approved(self):
        self.write({'state': 'not_approved'})



class LpjKasbonOperasionalLine(models.Model):
    _name = 'lpj.kasbon.operasional.line'
    _description = 'Lpj Kasbon Operasional Line'
    
    lpj_id = fields.Many2one('lpj.kasbon.operasional', string='LPJ', ondelete='cascade')
    no_sequence = fields.Integer('No.', compute="_sequence_ref", readonly=True)
    date = fields.Date('Tanggal', default=fields.Date.today())
    ket = fields.Char('Keterangan')
    account_id = fields.Many2one('account.account', string='Akun', ondelete='restrict')
    jumlah = fields.Float('Jumlah')
    currency_id = fields.Many2one('res.currency', string='Curenncy', compute='_compute_currency_id', store=True)
    diserahkan_id = fields.Many2one('hr.employee', string='Diserahkan oleh', compute='_compute_currency_id')

    @api.depends('lpj_id.currency_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.lpj_id.currency_id or rec.lpj_id.company_id.currency_id
            diserahkan_id = False
            if rec.lpj_id.diserahkan_id:
                diserahkan_id = rec.lpj_id.diserahkan_id
            rec.diserahkan_id = diserahkan_id


    @api.depends('lpj_id.lpj_line_ids', 'lpj_id.lpj_line_ids.date')
    def _sequence_ref(self):
        for line in self:
            no = 0
            for l in line.lpj_id.lpj_line_ids:
                no += 1
                l.no_sequence = no

    
