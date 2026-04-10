# Verify the sender email identity.
# In dev this uses SES sandbox — you must also manually verify recipient emails
# in the AWS SES console before sending test digests.
resource "aws_sesv2_email_identity" "sender" {
  email_identity = var.ses_sender_email

  tags = {
    Name = "${var.project}-ses-sender-${var.env}"
  }
}
