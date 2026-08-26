provider "aws" {
  region = var.aws_region
}

module "alexa_skill" {
  source   = "./modules/alexa-skill"
  for_each = var.skills

  skill_name     = each.key
  alexa_skill_id = each.value.alexa_skill_id
  source_dir     = each.value.source_dir
}
