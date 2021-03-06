action :create do

  ini = "#{new_resource.virtualenv}/eggcelerator.ini"
  s3cfg = "#{new_resource.virtualenv}/eggcelerator-s3cmd.ini"
  cmd = "#{new_resource.virtualenv}/bin/eggcelerator"
  cookbook = "eggcelerator"

  python_virtualenv "#{new_resource.virtualenv}" do
    action :create
    interpreter new_resource.interpreter
    owner new_resource.user
    group new_resource.group
  end

  template "#{ini}" do
    source "eggcelerator.ini.erb"
    cookbook cookbook
    owner new_resource.user
    group new_resource.group
    variables({ 
                :s3_cache => new_resource.s3_cache,
                :s3_config => s3cfg,
              })
  end

  template "#{s3cfg}" do
    source "s3cfg.erb"
    cookbook cookbook
    owner new_resource.user
    group new_resource.group
    variables({ 
                :aws_access => new_resource.aws_access,
                :aws_secret => new_resource.aws_secret,
              })
  end

  python_pip "#{new_resource.virtualenv}-install-eggcelerator" do
    action :install
    package_name "Eggcelerator"
    virtualenv new_resource.virtualenv
  end

  execute "#{new_resource.virtualenv}-execute" do
    command "#{cmd} -c #{ini} -r #{new_resource.requirements}"
    user new_resource.user
    environment({'HOME' => new_resource.home })
  end
end
