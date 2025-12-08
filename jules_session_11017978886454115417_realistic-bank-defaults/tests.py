import unittest
from app import app, db, User, Invoice, Boleto, BankConfig
from services import CnabService, BoletoBuilder
from datetime import date

class TestFidcSystem(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for testing
        self.app = app.test_client()
        with app.app_context():
            db.create_all()
            user = User(username='test_cedente', password_hash='hash', role='cedente')
            db.session.add(user)
            db.session.commit()
            
            # Setup configs
            conf = BankConfig(user_id=user.id, bank_type='santander', agency='1234', account='12345', wallet='101')
            db.session.add(conf)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_cnab_santander_format(self):
        # Create a mock user/config object structure for the service
        class MockConfig:
            username = 'TestUser'
            agency = '1234'
            account = '12345678'
            wallet = '101'
            
        user = MockConfig()
        
        boleto = Boleto(
            nosso_numero='123456789012', 
            amount=100.50, 
            sacado_name='Test Sacado',
            due_date=date(2023, 12, 31)
        )
        content = CnabService.generate_santander_240([boleto], user)
        # Check line length
        lines = content.split('\r\n')
        self.assertEqual(len(lines[0]), 240)
        self.assertIn('SANTANDER', lines[0])

    def test_cnab_bmp_format(self):
        class MockBankConfig:
            bank_type = 'bmp'
            agency = '0001'
            account = '12345-1'
            wallet = '109'
            convenio = '102030'

        class MockUser:
            username = 'TestUserBMP'
            bank_configs = [MockBankConfig()]
            
        user = MockUser()
        
        boleto = Boleto(
            id=1,
            nosso_numero='12345678901', 
            amount=200.00, 
            sacado_name='Test Sacado BMP',
            sacado_doc='12345678000199',
            due_date=date(2023, 12, 31)
        )
        content = CnabService.generate_bmp_400([boleto], user)
        lines = content.split('\r\n')
        self.assertEqual(len(lines[0]), 400)
        self.assertIn('BMP', lines[0])

    def test_santander_nosso_numero_logic(self):
        # Just check if it returns a string with hyphen
        nn = BoletoBuilder.calculate_santander_nosso_numero(123)
        self.assertTrue('-' in nn)

if __name__ == '__main__':
    unittest.main()
