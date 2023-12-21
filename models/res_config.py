from odoo import api, Command, fields, models, _, tools

class ResConfigSettings(models.Model):
    _name = 'kasbon.settings'
    _inherit = 'res.config.settings'

    akun_hutang_id = fields.Many2one('account.account', readonly=False, related='company_id.akun_hutang_id', string='Akun Hutang')

class ResCompany(models.Model):
    _inherit = 'res.company'

    akun_hutang_id = fields.Many2one('account.account', string='Akun Hutang')

    
