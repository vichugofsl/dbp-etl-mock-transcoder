.PHONY: deploy undeploy

deploy: clean build
	sls deploy --stage ${environment} 

undeploy:
	sls remove
