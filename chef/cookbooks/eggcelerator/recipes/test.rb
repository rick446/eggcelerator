execute "apt-get-update-periodic" do
  command "apt-get update"
  ignore_failure true
end

package "python-dev"
package "libpq-dev"

directory "#{node.home}/env" do
  owner node.user
  group node.group
  mode "0755"
  recursive true
  action :create
end

eggcelerator "#{node.virtualenv}" do
  action :create
  s3_cache node.s3_cache
  aws_access node.aws_access
  aws_secret node.aws_secret
  virtualenv node.virtualenv
  requirements node.requirements
  user node.user
  group node.group
  home node.home
end

# eggcelerator "#{node.virtualenv}-1" do
#   action :create
#   s3_cache node.s3_cache
#   aws_access node.aws_access
#   aws_secret node.aws_secret
#   virtualenv node.virtualenv
#   requirements node.requirements
#   user node.user
#   group node.group
#   home node.home
# end

# eggcelerator "#{node.virtualenv}-2" do
#   action :create
#   s3_cache node.s3_cache
#   aws_access node.aws_access
#   aws_secret node.aws_secret
#   virtualenv node.virtualenv
#   requirements node.requirements
#   user node.user
#   group node.group
#   home node.home
# end
