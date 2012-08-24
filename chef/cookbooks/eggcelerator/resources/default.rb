actions :create

attribute :virtualenv, :kind_of => String, :name_attribute => true
attribute :s3_cache, :kind_of => String
attribute :requirements, :kind_of => String
attribute :user, :kind_of => String
attribute :group, :kind_of => String
attribute :home, :kind_of => String
attribute :aws_access, :kind_of => String
attribute :aws_secret, :kind_of => String
