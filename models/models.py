# -*- coding: utf-8 -*-

from num2words import num2words
from odoo import api, Command, fields, models, _, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html2plaintext


from odoo.osv import expression
from odoo.tools.float_utils import float_is_zero
from bisect import bisect_left
from collections import defaultdict
from datetime import date
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
    

    is_kasbon = fields.Boolean('NPB / NPUM')
    is_lpj_kasbon = fields.Boolean('LPJ Kasbon Operaional')
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
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    # def default_diterima(self):
    #     diterima = False
    #     if self.env.user.employee_id:
    #         diterima = self.env.user.employee_id.id
    #     return diterima
    
    def default_journal(self):
        journal = False
        journal_id = self.env['account.journal'].search(['|', ('is_kasbon', '=', True), ('code', 'ilike', 'BILL')], limit=1)
        if journal_id:
            journal = journal_id.id
        return journal
    
    def default_account_credit(self):
        account_credit_kasbon_id = False
        akun_hutang = self.env.user.company_id.akun_hutang_id
        if akun_hutang:
            account_credit_kasbon_id = akun_hutang.id
        return account_credit_kasbon_id
    
    account_credit_kasbon_id = fields.Many2one('account.account', string='Akun Hutang', ondelete='restrict', default=default_account_credit, tracking=True)
    account_domain = fields.Many2many('account.account', string='Akun Domain', compute='_compute_akun_domain', tracking=True)
    date = fields.Date('Tanggal', default=fields.Date.today(), tracking=True)
    name = fields.Char('Nomor', default="/", copy=False, tracking=True)
    bisnis_unit_id = fields.Many2one('res.company', string='Bisnis Unit', default=lambda self: self.env.company, tracking=True)
    department_id = fields.Many2one('hr.department', string='Departemen', default=lambda self: self.env.user.department_id, tracking=True)
    analytic_id = fields.Many2one('account.analytic.account', string='Proyek', tracking=True)
    analytic_distribution = fields.Json(string='Proyek',tracking=True)
    analytic_precision = fields.Integer(string='Analytic Precision', store=False, default=lambda self: self.env['decimal.precision'].precision_get("Percentage Analytic"),tracking=True)
    kasbon_operasional_ids = fields.One2many('kasbon.operasional.line', 'kasbon_id', string='Kasbon Operasional Line',tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submission', 'Submission'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
    ], string='Status', default="draft", tracking=True)
    kasbon_type = fields.Selection([
        ('npb', 'NPB'),
        ('npum', 'NPUM')
    ], string='Tipe', default='npb', tracking=True)
    analytic_distribution_convert_to_char = fields.Char('Analytic Distribution Convert to Char', compute='_compute_convert_chart')
    
    company_id = fields.Many2one('res.company', string='Bisnis Unit', default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Curenncy', compute='_compute_currency_id', store=True, tracking=True)
    journal_id = fields.Many2one('account.journal', string='Journal', default=default_journal, ondelete='restrict')
    move_id = fields.Many2one('account.move', string='Journal Entries', ondelete='restrict', tracking=True)
    
    terbilang = fields.Char('Terbilang :', compute="amount_to_words", readonly=True, tracking=True)
    note = fields.Text('Note', tracking=True)
    total = fields.Float('Total :', compute="amount_to_words", readonly=True, store=True, tracking=True)

    diketahui_id = fields.Many2one('hr.employee', string='Diketahui oleh')
    disetujui_id = fields.Many2one('hr.employee', string='Disetujui oleh')
    diserahkan_id = fields.Many2one('hr.employee', string='Diserahkan oleh')
    diterima_id = fields.Many2one('hr.employee', string='Diterima oleh')

    kasbon_payments_widget = fields.Binary(
        related='move_id.invoice_payments_widget',
        exportable=False,
    )

    amount_residual = fields.Monetary(
        related='move_id.amount_residual',
        string='Amount Due',
    )

    payment_state = fields.Selection(
        related='move_id.payment_state',
        string="Payment Status",
    )


    @api.depends('analytic_distribution')
    def _compute_convert_chart(self):
        for record in self:
            analytic_distribution = ''
            if record.analytic_distribution:
                distibution_ids = []
                for distibution in list(record.analytic_distribution):
                    distibution_ids.append(int(float(distibution.replace(',', '.'))))
                
                anlytic = self.env['account.analytic.account'].browse(distibution_ids).mapped('name')
                if anlytic:
                    analytic_distribution = " / ".join(anlytic)
            record.analytic_distribution_convert_to_char = analytic_distribution


    @api.depends('company_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.company_id.currency_id

    @api.onchange('kasbon_type')
    def _onchange_kasbon_type(self):
        if self.kasbon_operasional_ids:
            self.kasbon_operasional_ids = [Command.clear()]

    @api.depends('department_id','kasbon_type')
    def _compute_akun_domain(self):
        for rec in self:
            rec.account_domain = [Command.clear()]
            if rec.department_id:
                if rec.kasbon_type == 'npb':
                    if rec.department_id.npb_account_ids:
                        rec.account_domain = [Command.set(rec.department_id.npb_account_ids.ids)]
                    else:
                        raise UserError('Departemen tidak memiliki akun untuk NPB')
                else:
                    if rec.department_id.npum_account_id:
                        rec.account_domain = [Command.set(rec.department_id.npum_account_id.ids)]
                    else:
                        raise UserError('Departemen tidak memiliki akun untuk NPUM')
            else:
                rec.account_domain = False


    @api.depends('kasbon_operasional_ids', 'kasbon_operasional_ids.jumlah')
    def amount_to_words(self):
        for rec in self:
            total = sum([x.jumlah for x in rec.kasbon_operasional_ids])
            rec.terbilang = num2words(int(total), to='currency', lang='id')
            rec.total = total

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            name = self.env['ir.sequence'].next_by_code('kasbon.operasional')
            if vals['kasbon_type']:
                if vals['kasbon_type'] == 'npb':
                    name = name.replace('KSB', 'NPB')
                else:
                    name = name.replace('KSB', 'NPUM')
            vals['name'] = name
        res = super(KasbonOperasional, self).create(vals_list)
        return res
    
    def set_to_draft(self):
        self.write({'state': 'draft'})
        if self.move_id:
            self.move_id.button_draft()
            self.move_id.button_cancel()
            self.move_id = False
    
    def set_to_cancel(self):
        self.write({'state': 'cancel'})
        if self.move_id:
            self.move_id.button_draft()
            self.move_id.button_cancel()
            self.move_id = False
    
    def set_to_submission(self):
        akun_hutang = self.env.user.company_id.akun_hutang_id
        if akun_hutang:
            self.write({
                'state': 'submission',
                'account_credit_kasbon_id': akun_hutang.id
            })
        else:
            raise UserError('Akun hutang belum ditambahkan.')

    def set_to_done(self):
        self = self.sudo()
        self.write({'state': 'done'})
        journal = self.journal_id if self.journal_id else self.env['account.journal'].search([('is_kasbon', '=', True)], limit=1)
        partner = self.bisnis_unit_id.partner_id
        today = date.today()

        if journal:
            create_vendor_bill = self.env['account.move'].create({
                'ref': self.name,
                'journal_id': journal.id,
                'partner_id': partner.id,
                'move_type': 'in_invoice',
                'invoice_date': today,
            })
        else:
            raise UserError('Tidak ada jurnal untuk NPB / NPUM')
        
        if create_vendor_bill:
            for bon in self.kasbon_operasional_ids:
                create_vendor_bill.invoice_line_ids = [Command.create({
                    'account_id': bon.account_id.id,
                    'currency_id': self.currency_id.id,
                    'name': bon.name,
                    'analytic_distribution': self.analytic_distribution,
                    'price_unit': bon.jumlah,
                })]

            # REPLACE PAYABLE ACCOUNT TO AKUN HUTANG
            def_acc = create_vendor_bill.partner_id.property_account_payable_id
            pay_acc = create_vendor_bill.line_ids.filtered(lambda x: x.account_id.account_type == 'liability_payable' and x.account_id.id == def_acc.id)
            if pay_acc:
                pay_acc.write({
                    'account_id': self.account_credit_kasbon_id.id,
                    'analytic_distribution': self.analytic_distribution,
                })

            self.move_id = create_vendor_bill.id
            create_vendor_bill.action_post()


    # def set_to_not_approved(self):
    #     self.write({'state': 'not_approved'})

    def create_payment_kasbon(self):
        if self.move_id:
            self = self.sudo()
            return self.move_id.line_ids.action_register_payment()
        else:
            raise UserError('Tidak ada Bill.')
        
    def action_open_business_doc(self):
        self = self.sudo()
        move = self.move_id
        return move.action_open_business_doc()

    def js_remove_outstanding_partial(self, partial_id):
        self = self.sudo()
        move = self.move_id
        return move.js_remove_outstanding_partial(partial_id)



class KasbonOperasionalLine(models.Model):
    _name = 'kasbon.operasional.line'
    _description = 'Kasbon Operasional Line'
    
    kasbon_id = fields.Many2one('kasbon.operasional', string='kasbon', ondelete='cascade')
    name = fields.Char('Uraian')
    account_id = fields.Many2one('account.account', string='Akun')
    jumlah = fields.Float('Jumlah')

    @api.onchange('name', 'jumlah')
    def _onchange_name_jumlah(self):
        if self.kasbon_id.kasbon_type == 'npum':
            self.account_id = self.kasbon_id.department_id.npum_account_id.id
    
class LpjKasbonOperasional(models.Model):
    _name = 'lpj.kasbon.operasional'
    _description = 'Lpj Kasbon Operasional'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    # def default_diterima(self):
    #     diterima = False
    #     if self.env.user.employee_id:
    #         diterima = self.env.user.employee_id.id
    #     return diterima
    
    def default_journal(self):
        journal = False
        journal_id = self.env['account.journal'].search([('is_lpj_kasbon', '=', True)], limit =1)
        if journal_id:
            journal = journal_id.id
        return journal
    
    name = fields.Char('Name', default="Draft", copy=False, tracking=True)
    date = fields.Date('Tanggal', default=fields.Date.today(), tracking=True)
    kasbon_id = fields.Many2one('kasbon.operasional', string='No. Kasbon', domain=[('state', '=', 'done')], ondelete='restrict', tracking=True)
    bisnis_unit_id = fields.Many2one('res.company', string='Bisnis Unit', default=lambda self: self.env.company, tracking=True)
    department_id = fields.Many2one('hr.department', string='Departemen', default=lambda self: self.env.user.department_id, tracking=True)
    analytic_id = fields.Many2one('account.analytic.account', string='Proyek', tracking=True)
    analytic_distribution = fields.Json(string='Proyek', tracking=True)
    analytic_precision = fields.Integer(string='Analytic Precision', store=False, default=lambda self: self.env['decimal.precision'].precision_get("Percentage Analytic"), tracking=True)
    lpj_line_ids = fields.One2many('lpj.kasbon.operasional.line', 'lpj_id', string='LPJ Line', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submission', 'Submission'),
        ('done', 'Done'),
        ('cancel', 'Cancel'),
    ], string='state', default="draft", tracking=True)
    analytic_distribution_convert_to_char = fields.Char('Analytic Distribution Convert to Char', compute='_compute_convert_chart', tracking=True)

    note = fields.Text('Note', tracking=True)
    jumlah_kasbon = fields.Float('Jumlah Kasbon', related='kasbon_id.total', tracking=True)
    total_pertanggungjawaban = fields.Float('Total Pertanggungjawaban', readonly=True, store=True, compute="amount_to_words", tracking=True)
    lebih_kurang_bayar = fields.Float('Lebih/(Kurang) Bayar', readonly=True, store=True, compute="amount_to_words")

    company_id = fields.Many2one('res.company', string='Bisnis Unit', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Curenncy', compute='_compute_currency_id')
    journal_id = fields.Many2one('account.journal', string='Journal', default=default_journal, ondelete='restrict')
    move_id = fields.Many2one('account.move', string='Journal Entries', ondelete='restrict', tracking=True)

    # diserahkan_id = fields.Many2one('hr.employee', string='Diserahkan oleh', default=default_diterima)
    # diperiksa_id = fields.Many2one('hr.employee', string='Diperikasa oleh')
    # disetujui_id = fields.Many2one('hr.employee', string='Disetujui oleh')
    # dibukukan_id = fields.Many2one('hr.employee', string='Dibukukan oleh')

    lpj_payments_widget = fields.Binary(
        related='move_id.invoice_payments_widget',
        exportable=False,
        tracking=True,
    )

    # amount_residual = fields.Monetary(
    #     related='move_id.amount_residual',
    #     string='Amount Due',
    # )

    payment_state = fields.Selection(
        related='move_id.payment_state',
        string="Payment Status",
        tracking=True,
    )

    @api.depends('analytic_distribution')
    def _compute_convert_chart(self):
        for record in self:
            analytic_distribution = ''
            if record.analytic_distribution:
                distibution_ids = []
                for distibution in list(record.analytic_distribution):
                    distibution_ids.append(int(float(distibution.replace(',', '.'))))
                
                anlytic = self.env['account.analytic.account'].browse(distibution_ids).mapped('name')
                if anlytic:
                    analytic_distribution = " / ".join(anlytic)
            record.analytic_distribution_convert_to_char = analytic_distribution
    
    @api.depends('journal_id.currency_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.company_id.currency_id
            # rec.currency_id = rec.journal_id.currency_id.id or rec.company_id.currency_id.id

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


    def create_payment_lpj(self):
        if self.move_id:
            self = self.sudo()
            return self.move_id.line_ids.action_register_payment()
        else:
            raise UserError('Tidak ada Bill.')
    
    def set_to_draft(self):
        self.write({'state': 'draft'})
        if self.move_id:
            self.move_id.button_draft()
            self.move_id.button_cancel()
            self.move_id = False

    def set_to_cancel(self):
        self.write({'state': 'cancel'})
        if self.move_id:
            self.move_id.button_draft()
            self.move_id.button_cancel()
            self.move_id = False

    def set_to_submission(self):
        self.write({'state': 'submission'})
        self.name = self.env['ir.sequence'].next_by_code('lpj.kasbon.operasional')

    def set_to_done(self):
        self = self.sudo()
        self.write({'state': 'done'})
        journal = self.journal_id if self.journal_id else self.env['account.journal'].search([('is_lpj_kasbon', '=', True)], limit=1)
        partner = self.bisnis_unit_id.partner_id
        today = date.today()

        # if create_journal_entries:
        #     lines = []
        #     for rec in self.lpj_line_ids:
        #         lines.append((0, 0, {
        #             'account_id': rec.account_id.id,
        #             'currency_id': rec.currency_id.id,
        #             'name': "LPJ Kasbon %s %s %s - %s - %s" % (rec.ket, rec.currency_id.symbol, str(rec.jumlah), rec.diserahkan_id.name, str(rec.date)),
        #             'analytic_distribution': self.analytic_distribution,
        #             'debit': rec.jumlah,
        #             'credit': 0,
        #         }))
        #     lines.append((0, 0, {
        #         'account_id': self.journal_id.account_credit_lpj_kasbon_id.id,
        #         'currency_id': self.currency_id.id,
        #         'name': "LPJ Kasbon Operasional %s %s - %s - %s" % (self.currency_id.symbol, str(self.total_pertanggungjawaban), self.diserahkan_id.name, str(self.date)),
        #         'analytic_distribution': self.analytic_distribution,
        #         'debit': 0,
        #         'credit': self.total_pertanggungjawaban,
        #     }))
        #     print("=========", lines)
        #     create_journal_entries.write({'line_ids': lines})
        #     self.move_id = create_journal_entries.id
        #     create_journal_entries.action_post()

        if journal:
            create_vendor_bill = self.env['account.move'].create({
                'ref': self.name,
                'journal_id': journal.id,
                'partner_id': partner.id,
                'move_type': 'in_invoice',
                'invoice_date': today,
            })
        else:
            raise UserError('Tidak ada jurnal untuk LPJ')
        
        if create_vendor_bill:
            for bon in self.lpj_line_ids:
                create_vendor_bill.invoice_line_ids = [Command.create({
                    'account_id': bon.account_id.id,
                    'currency_id': bon.currency_id.id,
                    'name': bon.ket,
                    'analytic_distribution': self.analytic_distribution,
                    'price_unit': bon.jumlah,
                })]

            # REPLACE PAYABLE ACCOUNT TO AKUN HUTANG
            def_acc = create_vendor_bill.partner_id.property_account_payable_id
            pay_acc = create_vendor_bill.line_ids.filtered(lambda x: x.account_id.account_type == 'liability_payable' and x.account_id.id == def_acc.id)
            if pay_acc:
                pay_acc.write({
                    'account_id': self.kasbon_id.account_credit_kasbon_id.id,
                    'analytic_distribution': self.analytic_distribution,
                })

            self.move_id = create_vendor_bill.id
            create_vendor_bill.action_post()


    # def set_to_approved_1(self):
    #     self.write({'state': 'approved_1'})

    # def set_to_approved_2(self):
    #     self.write({'state': 'approved_2'})

    # def set_to_not_approved(self):
    #     self.write({'state': 'not_approved'})


class LpjKasbonOperasionalLine(models.Model):
    _name = 'lpj.kasbon.operasional.line'
    _description = 'Lpj Kasbon Operasional Line'
    
    lpj_id = fields.Many2one('lpj.kasbon.operasional', string='LPJ', ondelete='cascade')
    no_sequence = fields.Integer('No.', compute="_sequence_ref", readonly=True)
    date = fields.Date('Tanggal', default=fields.Date.today())
    ket = fields.Char('Keterangan')
    account_id = fields.Many2one('account.account', string='Akun', ondelete='restrict')
    jumlah = fields.Float('Jumlah')
    currency_id = fields.Many2one('res.currency', string='Currency', compute='_compute_currency_id', store=True)
    # diserahkan_id = fields.Many2one('hr.employee', string='Diserahkan oleh', compute='_compute_currency_id')

    @api.depends('lpj_id.currency_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.lpj_id.currency_id or rec.lpj_id.company_id.currency_id
            # diserahkan_id = False
            # if rec.lpj_id.diserahkan_id:
            #     diserahkan_id = rec.lpj_id.diserahkan_id
            # rec.diserahkan_id = diserahkan_id


    @api.depends('lpj_id.lpj_line_ids', 'lpj_id.lpj_line_ids.date')
    def _sequence_ref(self):
        for line in self:
            no = 0
            for l in line.lpj_id.lpj_line_ids:
                no += 1
                l.no_sequence = no

    
class HrDepartment(models.Model):
    _inherit = 'hr.department'
    
    npb_account_ids = fields.Many2many('account.account', string='NPB Accounts')
    npum_account_id = fields.Many2one('account.account', string='NPUM Account')
